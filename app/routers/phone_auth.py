# app/routers/phone_auth.py
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ..database import get_db
from .. import models, utils, oauth2
from ..sms_utils import generate_otp, send_otp_sms

router = APIRouter(prefix="/auth/phone", tags=["Phone Verification"])

OTP_EXPIRE_MINUTES = 10


# ---------------------------------------------------------
# Schemas
# ---------------------------------------------------------
class RequestOTP(BaseModel):
    phone_number: str = Field(..., pattern=r"^\+?[1-9]\d{1,14}$", example="+2348065310078")

class VerifyOTP(BaseModel):
    phone_number: str = Field(..., pattern=r"^\+?[1-9]\d{1,14}$", example="+2348065310078")
    otp: str = Field(..., min_length=6, max_length=6, example="123456")


# ---------------------------------------------------------
# Endpoints
# ---------------------------------------------------------
@router.post("/send-otp", status_code=status.HTTP_200_OK)
def send_phone_otp(
    payload: RequestOTP,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    phone = payload.phone_number.strip()
    
    # 1. Check if the user exists
    user = db.query(models.User).filter(models.User.phone_number == phone).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this phone number."
        )

    # 2. Invalidate previous unused OTPs for this number
    db.query(models.PhoneVerification).filter(
        models.PhoneVerification.phone_number == phone,
        models.PhoneVerification.is_used == False
    ).update({"is_used": True})

    # 3. Generate OTP and save hash
    otp_code = generate_otp()
    hashed_code = utils.hash(otp_code)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)

    verification_record = models.PhoneVerification(
        phone_number=phone,
        otp_hash=hashed_code,
        expires_at=expires_at,
        is_used=False
    )
    db.add(verification_record)
    db.commit()

    # 4. Dispatch SMS in background
    background_tasks.add_task(send_otp_sms, phone, otp_code, OTP_EXPIRE_MINUTES)

    return {"status": "success", "detail": f"OTP has been sent to {phone}"}


@router.post("/verify-otp")
def verify_phone_otp(payload: VerifyOTP, db: Session = Depends(get_db)):
    phone = payload.phone_number.strip()
    submitted_otp = payload.otp.strip()

    # 1. Fetch latest active verification record
    record = (
        db.query(models.PhoneVerification)
        .filter(
            models.PhoneVerification.phone_number == phone,
            models.PhoneVerification.is_used == False
        )
        .order_by(models.PhoneVerification.created_at.desc())
        .first()
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active OTP found for this phone number."
        )

    # 2. Check expiration
    now = datetime.now(timezone.utc)
    record_expiry = record.expires_at.replace(tzinfo=timezone.utc) if record.expires_at.tzinfo is None else record.expires_at

    if now > record_expiry:
        record.is_used = True
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired. Please request a new code."
        )

    # 3. Verify OTP Hash
    if not utils.verify(submitted_otp, record.otp_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP code."
        )

    # 4. Mark OTP as consumed
    record.is_used = True

    # 5. Activate / Verify User
    user = db.query(models.User).filter(models.User.phone_number == phone).first()
    if user:
        user.is_verified = True
        user.is_active = True

    db.commit()

    # 6. Return JWT access token
    access_token = oauth2.create_access_token(data={"user_id": user.id})
    return {
        "status": "success",
        "detail": "Phone verified successfully.",
        "access_token": access_token,
        "token_type": "bearer"
    }