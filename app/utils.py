from datetime import datetime, timedelta, timezone
import random
import re
import string
import requests
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from . import models
from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def normalize_phone_number(
    phone: str, default_country_code: str = "+234"
) -> str:
    """Normalizes local Nigerian numbers (080...) to E.164 (+23480...)."""
    cleaned = re.sub(r"[\s\-\(\)]", "", phone.strip())
    if cleaned.startswith("0") and len(cleaned) == 11:
        return f"{default_country_code}{cleaned[1:]}"
    if not cleaned.startswith("+"):
        return f"+{cleaned}"
    return cleaned


def format_nigerian_phone_no_plus(phone: str) -> str:
    """Formats local Nigerian phone numbers to standard international
    format without '+' — this is the format Kudisms expects in `recipients`."""
    normalized = normalize_phone_number(phone)
    return normalized.lstrip("+")


def hash(password: str) -> str:
    """Hashes a raw password."""
    return pwd_context.hash(password)


def verify(plain_password: str, hashed_password: str) -> bool:
    """Verifies a raw password against its stored hash."""
    return pwd_context.verify(plain_password, hashed_password)


def send_kudisms_otp(
    phone: str,
    otp_length: int = 6,
    otp_duration: int = 5,
    otp_attempts: int = 3,
    channel: str = "sms",
) -> dict:
    """
    Asks Kudisms to generate and dispatch an OTP to the given phone number.
    Kudisms owns the OTP itself (generation, expiry, attempt counting) —
    we only ever store the verification_id it hands back.

    Returns:
        {"success": True, "verification_id": "..."} on success
        {"success": False, "error": "...", "error_code": "..."} on failure
    """
    formatted_phone = format_nigerian_phone_no_plus(phone)
    url = f"{settings.KUDISMS_BASE_URL}/sendotp"

    fields = {
        "token": settings.KUDISMS_API_KEY,
        "senderID": settings.KUDISMS_SENDER_ID,
        "recipients": formatted_phone,
        "appnamecode": settings.KUDISMS_APP_NAME_CODE,
        "templatecode": settings.KUDISMS_TEMPLATE_CODE,
        "otp_type": "NUMERIC",
        "otp_length": str(otp_length),
        "otp_duration": str(otp_duration),
        "otp_attempts": str(otp_attempts),
        "channel": channel,
    }
    # Kudisms requires true multipart/form-data (like curl --form), not
    # urlencoded — data={} silently drops/misreads fields on their end.
    # The (None, value) trick makes `requests` send plain fields as
    # multipart parts without attaching an actual file.
    multipart_fields = {k: (None, v) for k, v in fields.items()}

    try:
        response = requests.post(url, files=multipart_fields, timeout=10)
        data = response.json()

        if data.get("status") == "success" and data.get("verification_id"):
            print(f"[KUDISMS SENDOTP SUCCESS] {data}")
            return {"success": True, "verification_id": data["verification_id"]}

        # Covers Kudisms error codes like 109 (insufficient balance),
        # 188 (unapproved sender ID), 300 (missing parameter), etc.
        print(f"[KUDISMS SENDOTP ERROR] Status {response.status_code}, Body: {data}")
        return {
            "success": False,
            "error": data.get("msg", "Failed to send OTP"),
            "error_code": data.get("error_code"),
        }

    except Exception as e:
        print(f"[KUDISMS SENDOTP ERROR] Exception: {e}")
        return {"success": False, "error": str(e), "error_code": None}


def verify_kudisms_otp(verification_id: str, otp: str) -> dict:
    """
    Verifies a user-entered OTP against Kudisms.

    Returns:
        {"success": True, "msg": "...", "raw": {...}}
        {"success": False, "msg": "...", "raw": {...}}
    """
    url = f"{settings.KUDISMS_BASE_URL}/verifyotp"
    fields = {
        "token": settings.KUDISMS_AUTH_TOKEN,
        "verification_id": verification_id,
        "otp": otp,
    }
    multipart_fields = {k: (None, v) for k, v in fields.items()}

    try:
        response = requests.post(url, files=multipart_fields, timeout=10)
        data = response.json()

        success = data.get("status") == "success"
        if not success:
            print(f"[KUDISMS VERIFYOTP ERROR] Status {response.status_code}, Body: {data}")

        return {"success": success, "msg": data.get("msg"), "raw": data}

    except Exception as e:
        print(f"[KUDISMS VERIFYOTP ERROR] Exception: {e}")
        return {"success": False, "msg": str(e), "raw": {}}