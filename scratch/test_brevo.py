import requests
import sys

api_key = "YOUR_API_KEY_HERE"

url = "https://api.brevo.com/v3/smtp/email"

payload = {
    "sender": {
        "name": "Josue Test",
        "email": "no-reply@payparo.tech"
    },
    "to": [
        {
            "email": "thatsariful@gmail.com",
            "name": "Sariful"
        }
    ],
    "subject": "Brevo API Test",
    "htmlContent": "<html><body><h1>This is a test email via Brevo API</h1></body></html>"
}

headers = {
    "accept": "application/json",
    "api-key": api_key,
    "content-type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)

print("Status Code:", response.status_code)
print("Response:", response.text)
