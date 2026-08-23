import secrets
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from .config import settings
from . import utils

# Initialize Twilio Client
twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def generate_otp() -> str:
    """Generates a 6-digit numerical string."""
    return f"{secrets.randbelow(1_000_000):06d}"


def send_otp_sms(to_phone: str, otp_code: str, expiry_minutes: int = 10) -> bool:
    """Sends SMS via Twilio API."""
    body_text = f"Your verification code is {otp_code}. It expires in {expiry_minutes} minutes."
    try:
        twilio_client.messages.create(
            body=body_text,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=to_phone
        )
        return True
    except TwilioRestException as exc:
        print(f"[ERROR] Twilio SMS dispatch failed: {exc.msg}")
        return False