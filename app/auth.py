from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from . import models, schemas, utils, oauth2, email_utils
from .database import get_db

router = APIRouter(prefix="/auth", tags=["Login"])


def format_nigerian_phone(phone: str) -> str:
    clean_phone = phone.strip().replace(" ", "").replace("-", "")
    if clean_phone.startswith("0"):
        return f"234{clean_phone[1:]}"
    elif clean_phone.startswith("+234"):
        return clean_phone[1:]
    elif clean_phone.startswith("234"):
        return clean_phone
    return clean_phone


def _get_user_by_identifier(db: Session, email: str | None, phone_number: str | None):
    filters = []
    if email:
        filters.append(models.User.email == email.strip())
    if phone_number:
        raw_phone = phone_number.strip()
        formatted_phone = format_nigerian_phone(raw_phone)
        filters.append(models.User.phone_number == raw_phone)
        filters.append(models.User.phone_number == formatted_phone)
    if not filters:
        return None
    return db.query(models.User).filter(or_(*filters)).first()


def _send_verification(db: Session, user: models.User, purpose: str = "signup"):
    otp = utils.generate_otp()
    message = f"Your Wenyfour {purpose} code is: {otp}"

    if user.email:
        email_utils.send_confirmation_email(user.email, user.full_name or "User", message)
    elif user.phone_number:
        utils.send_sms_kudisms(user.phone_number, message)


def _issue_token(user: models.User) -> dict:
    access_token = oauth2.create_access_token(data={"user_id": user.id})
    role_str = user.role.value if hasattr(user.role, 'value') else str(user.role)
    roles = [{
        "role": role_str,
        "profile_complete": user.profile_complete,
        "verification_status": None
    }]
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "active_role": role_str,
        "roles": roles
    }


@router.post("/login")
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    user = _get_user_by_identifier(db, payload.email, payload.phone_number)
    if not user or not utils.verify(payload.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Please verify your account first.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your account is deactivated.")
    return _issue_token(user)