import requests
import sys

# Login
login_url = "http://localhost:8000/api/v1/account/login/"
data = {"email": "contract.manager@gmail.com", "password": "password123"}
r = requests.post(login_url, json=data)
if r.status_code != 200:
    print("Login failed", r.text)
    sys.exit(1)

token = r.json().get('access')
if not token:
    print("No token", r.json())
    sys.exit(1)

# Fetch
url = "http://localhost:8000/api/v1/contracts-manager/projects/"
headers = {"Authorization": f"Bearer {token}"}
r = requests.get(url, headers=headers)
print("Status:", r.status_code)
print("Response:", r.json())
