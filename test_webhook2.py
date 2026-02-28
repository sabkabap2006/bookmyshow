import urllib.request
import json
import ssl
import sys
import hmac
import hashlib

# 1. Provide your dummy secret and payload
secret = "akash2006".encode('utf-8')
payload = json.dumps({
    "event": "order.paid",
    "payload": {
        "payment": {
            "entity": {
                "id": "pay_fake123",
                "order_id": "order_fake123", # this must exist in DB for full test, but lets see if signature passes first
                "amount": 500,
                "currency": "INR",
                "status": "captured",
                "email": "sayantanpal2006741201@gmail.com",
                "contact": "+919999999999"
            }
        }
    }
}, separators=(',', ':')).encode('utf-8')

# 2. Generate the required Razorpay Signature Math
signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()

# 3. Fire the request
url = "https://bookmyshow-seven-lake.vercel.app/movies/payment/webhook/"
headers = {
    "Content-Type": "application/json",
    "X-Razorpay-Signature": signature
}
req = urllib.request.Request(url, data=payload, headers=headers)

try:
    print(f"Pinging {url} with valid signature math...")
    context = ssl._create_unverified_context()
    response = urllib.request.urlopen(req, context=context)
    print(f"Status: {response.status}")
    print(response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    print(e.read().decode('utf-8'))
except Exception as e:
    print(f"Error: {e}")
