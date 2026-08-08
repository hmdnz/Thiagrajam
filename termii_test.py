import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("TERMII_API_KEY")
sender_id = os.getenv("TERMII_SENDER_ID", "Termii")

if not api_key:
    raise SystemExit("TERMII_API_KEY not found — check your .env file")

response = requests.post(
    "https://api.ng.termii.com/api/sms/send",
    json={
        "api_key": api_key,
        "to": "2348065310078",
        "from": sender_id,
        "sms": "Your Wenyfour verification code is 123456. It expires in 10 minutes.",
        "type": "plain",
        "channel": "dnd",
    },
)

print(response.status_code)
print(response.json())