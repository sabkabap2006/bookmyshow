import urllib.request
import json
import ssl
import sys

url = "https://bookmyshow-seven-lake.vercel.app/movies/payment/webhook/"
data = {
    "event": "order.paid",
    "payload": {
        "payment": {
            "entity": {
                "id": "pay_fake123",
                "order_id": "order_fake123",
                "amount": 50000,
                "currency": "INR",
                "status": "captured",
                "email": "sayantanpal2006741201@gmail.com",
                "contact": "+919999999999"
            }
        }
    }
}
headers = {
    "Content-Type": "application/json",
    "X-Razorpay-Signature": "invalid_signature_just_testing_endpoint"
}
req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
try:
    print(f"Pinging {url}...")
    # bypass SSL for mac bug
    context = ssl._create_unverified_context()
    response = urllib.request.urlopen(req, context=context)
    print(f"Status: {response.status}")
    print(response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    print(e.read().decode('utf-8'))
except Exception as e:
    print(f"Error: {e}")
