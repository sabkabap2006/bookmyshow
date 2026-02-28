import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookmyseat.settings')
django.setup()

from movies.tasks import send_booking_confirmation_email

# Verify API key is loaded
from django.conf import settings
print("Checking API Key:")
key = getattr(settings, 'SENDGRID_API_KEY', None) or os.environ.get('SENDGRID_API_KEY')
if not key:
    print("ERROR: SENDGRID_API_KEY is not found in local environment.")
else:
    print(f"Found API key starting with: {key[:8]}...")

# Fire the real function directly
demo_data = {
    'movie_name': 'Test Movie Authentication',
    'theater_name': 'Test Theater',
    'show_date': '2026-03-01',
    'show_time': '12:00 PM',
    'seats': 'A1, A2',
    'amount': 500,
    'payment_id': 'pay_test123'
}
sayantans_email = "sayantanpal2006741201@gmail.com"

print(f"\nSending demo email to {sayantans_email}...")
result = send_booking_confirmation_email(sayantans_email, demo_data)

if result:
    print("\n✅ PYTHON SCRIPT SAYS SUCCESS! Check your inbox.")
else:
    print("\n❌ EMAIL FAILED.")
