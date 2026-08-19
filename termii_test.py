import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("TERMII_API_KEY")
sender_id = os.getenv("TERMII_SENDER_ID")

if not api_key:
    raise SystemExit("TERMII_API_KEY not found")

if not sender_id:
    raise SystemExit("TERMII_SENDER_ID not found")

response = requests.post(
    "https://v4.api.termii.com/api/v1/sms/send",
    json={
        "api_key": api_key,
        "to": "2348065310078",
        "from": sender_id,
        "sms": "Your Wenyfour verification code is 123456. It expires in 10 minutes.",
        "type": "plain",
        "channel": "dnd",
    },
    timeout=15,
)

print(response.status_code)
print(response.text)