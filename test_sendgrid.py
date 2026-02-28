import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bookmyseat.settings')
django.setup()

import urllib.request
import json
import ssl
from django.conf import settings

api_key = getattr(settings, 'SENDGRID_API_KEY', None) or os.environ.get('SENDGRID_API_KEY')
print(f"API key loaded: {bool(api_key)}")

payload = {
    "personalizations": [
        {
            "to": [{"email": "sayantanpal2006741201@gmail.com"}],
            "subject": "Test Debugger"
        }
    ],
    "from": {"email": "sayantanpal2006741201@gmail.com", "name": "BookMyShow"},
    "content": [
        {
            "type": "text/html",
            "value": "<h1>Test from debugger</h1>"
        }
    ]
}

req = urllib.request.Request('https://api.sendgrid.com/v3/mail/send')
req.add_header('Authorization', f'Bearer {api_key}')
req.add_header('Content-Type', 'application/json')
context = ssl._create_unverified_context()

try:
    print("Sending API request to SendGrid...")
    response = urllib.request.urlopen(req, json.dumps(payload).encode('utf-8'), context=context)
    print(f"Success! Status: {response.status}")
except urllib.error.HTTPError as e:
    print(f"\n❌ SENDGRID REJECTED THE REQUEST: HTTP {e.code}")
    print("\n--- SENDGRID ERROR REASON ---")
    error_body = e.read().decode('utf-8')
    try:
        # Try to make it pretty JSON if possible
        print(json.dumps(json.loads(error_body), indent=2))
    except:
        print(error_body)
    print("-----------------------------\n")
except Exception as e:
    print(f"Other Error: {e}")
