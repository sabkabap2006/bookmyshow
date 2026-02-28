import os
import sys
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookmyseat.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

print(f"Attempting to send test email as: {settings.EMAIL_HOST_USER}")

try:
    send_mail(
        subject='Test Email from BookMyShow Clone',
        message='If you are reading this, your Django email configuration is working perfectly!',
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[settings.EMAIL_HOST_USER],
        fail_silently=False,
    )
    print("SUCCESS: Test email sent successfully! Please check your inbox (and spam folder).")
except Exception as e:
    print(f"FAILED: Could not send email. Error: {str(e)}")
