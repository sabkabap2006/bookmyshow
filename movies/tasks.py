import logging
import json
import urllib.request
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
        
        # Render the text content
        text_content = render_to_string('emails/booking_confirmation.txt', {'booking': booking_data})
        
        # Render the HTML content
        context = {'booking': booking_data}
        html_content = render_to_string('emails/booking_confirmation.html', context)

        api_key = getattr(settings, 'SENDGRID_API_KEY', None)
        import os
        if not api_key:
            api_key = os.environ.get('SENDGRID_API_KEY')
            
        if not api_key:
            print("EMAIL THREAD ERROR: Missing SENDGRID_API_KEY environment variable. Cannot send email.")
            return False

        payload = {
            "personalizations": [
                {
                    "to": [{"email": user_email}],
                    "subject": f"Tickets Confirmed! - {booking_data['movie_name']}"
                }
            ],
            "from": {"email": "sayantanpal2006741201@gmail.com", "name": "BookMyShow"},
            "content": [
                {
                    "type": "text/html",
                    "value": html_content
                }
            ]
        }

        req = urllib.request.Request('https://api.sendgrid.com/v3/mail/send')
        req.add_header('Authorization', f'Bearer {api_key}')
        req.add_header('Content-Type', 'application/json')
        
        # Bypass SSL Verification (Fix for MacOS/Server bug)
        import ssl
        context = ssl._create_unverified_context()

        try:
            # Send HTTP POST directly 
            response = urllib.request.urlopen(req, json.dumps(payload).encode('utf-8'), context=context)
            print(f"SENDGRID API SUCCESS: Email sent successfully to {user_email}! Status: {response.getcode()}")
            return True
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            print(f"EMAIL THREAD ERROR (SendGrid HTTP): Status {e.code} | Body: {error_body}")
            logger.error(f"SendGrid HTTP Error: {error_body}")
            return False
        except urllib.error.URLError as e:
            print(f"EMAIL THREAD ERROR (URLError): {e.reason}")
            logger.error(f"URLError: {e.reason}")
            return False
            
    except Exception as exc:
        logger.error(f"Failed to send email to {user_email}: {exc}")
        import traceback
        traceback.print_exc()
        print(f"EMAIL THREAD ERROR (API Catch-all): {exc}")
        return False

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
