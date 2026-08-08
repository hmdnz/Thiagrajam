import random
import string
import time

# In-memory store simulating Termii's OTP tracking.
# Format: { pin_id: {"phone": str, "otp": str, "expires_at": float, "attempts": int} }
_MOCK_OTP_STORE = {}

OTP_LENGTH = 6
OTP_TTL_SECONDS = 600  # 10 minutes, matches your real Termii config
MAX_ATTEMPTS = 3


def send_otp(phone_number: str) -> str:
    """
    Mock of Termii's /sms/otp/send.
    Generates a fake pin_id + OTP, 'sends' it by printing to console,
    and returns pin_id — same contract as the real send_otp().
    """
    otp = "".join(random.choices(string.digits, k=OTP_LENGTH))
    pin_id = "mock-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=12))

    _MOCK_OTP_STORE[pin_id] = {
        "phone": phone_number,
        "otp": otp,
        "expires_at": time.time() + OTP_TTL_SECONDS,
        "attempts": 0,
    }

    print(f"[MOCK SMS] To: {phone_number} | OTP: {otp} | pin_id: {pin_id}")

    return pin_id


def verify_otp(pin_id: str, pin: str) -> bool:
    """
    Mock of Termii's /sms/otp/verify.
    Checks the in-memory store instead of calling the real API.
    """
    record = _MOCK_OTP_STORE.get(pin_id)

    if not record:
        return False

    if time.time() > record["expires_at"]:
        del _MOCK_OTP_STORE[pin_id]
        return False

    record["attempts"] += 1
    if record["attempts"] > MAX_ATTEMPTS:
        del _MOCK_OTP_STORE[pin_id]
        return False

    if record["otp"] == pin:
        del _MOCK_OTP_STORE[pin_id]  # one-time use, same as real OTPs
        return True

    return False