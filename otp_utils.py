import random
from datetime import datetime, timedelta
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

OTP_EXPIRE_MINUTES = 10


def generate_otp() -> str:
    """6-digit numeric OTP as a string, e.g. '048213'."""
    return f"{random.randint(0, 999999):06d}"


def hash_otp(otp: str) -> str:
    return pwd_context.hash(otp)


def verify_otp(plain_otp: str, hashed_otp: str) -> bool:
    return pwd_context.verify(plain_otp, hashed_otp)


def otp_expiry() -> datetime:
    return datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)