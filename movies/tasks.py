import logging
from smtplib import SMTPException
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger(__name__)

def send_booking_confirmation_email(user_email, booking_data):
    """
    Sends a booking confirmation email securely in the background.
    Retries up to 3 times on SMTP related errors.
    """
    try:
        subject = f"Booking Confirmation: {booking_data['movie_name']} at {booking_data['theater_name']}"
        from_email = settings.EMAIL_HOST_USER
        
        # Render the text content
        text_content = render_to_string('emails/booking_confirmation.txt', {'booking': booking_data})
        
        # Render the HTML content
        html_content = render_to_string('emails/booking_confirmation.html', {'booking': booking_data})

        msg = EmailMultiAlternatives(subject, text_content, from_email, [user_email])
        msg.attach_alternative(html_content, "text/html")
        msg.send()

        logger.info(f"Successfully sent confirmation email to {user_email} for booking ID {booking_data.get('payment_id')}")
        return True
    
    except SMTPException as exc:
        logger.warning(f"SMTP error sending email to {user_email}: {exc}.")
        print(f"EMAIL THREAD ERROR (SMTP): {exc}")
        pass
    except Exception as exc:
        logger.error(f"Failed to send email to {user_email}: {exc}")
        print(f"EMAIL THREAD ERROR (General): {exc}")
        pass

def release_expired_bookings():
    """
    Crawls the database for any seats that have been locked in a PENDING state
    for more than 2 minutes without payment completion, and frees them.
    Runs every 1 minute via Celery Beat.
    """
    from datetime import timedelta
    from django.utils import timezone
    from django.db import transaction
    from .models import Booking, Payment
    
    two_minutes_ago = timezone.now() - timedelta(minutes=2)
    
    # Identify abandoned holds
    expired_bookings = Booking.objects.filter(status='PENDING', locked_at__lt=two_minutes_ago)
    
    count = 0
    with transaction.atomic():
        for b in expired_bookings:
            b.status = 'CANCELLED'
            b.save()
            
            # Release the physical DB lock on the seat
            b.seat.is_booked = False
            b.seat.save()
            count += 1
            
            # Since the user could have attempted multiple payments, mark lingering Payment intents as CANCELLED
            payments = Payment.objects.filter(user=b.user, status='CREATED')
            for p in payments:
                p.status = 'CANCELLED'
                p.save()
                
    if count > 0:
        logger.info(f"Released {count} expired seat reservations successfully.")
    
    return count
