from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from . import models, schemas, utils, oauth2
from .database import get_db

router = APIRouter(prefix="/auth", tags=["Login"])

OTP_EXPIRE_MINUTES = 10
RESEND_COOLDOWN_SECONDS = 60
RESEND_MAX_PER_HOUR = 5


# ==========================================================
# Small helpers
# ==========================================================

def _get_user_by_identifier(db: Session, email: str | None, phone_number: str | None):
    filters = []
    if email:
        filters.append(models.User.email == email)
    if phone_number:
        filters.append(models.User.phone_number == phone_number)
    if not filters:
        return None
    return db.query(models.User).filter(or_(*filters)).first()


def _channel_for(email: str | None, phone_number: str | None) -> str:
    return "email" if email else "sms"


def _send_verification(db: Session, user: models.User, purpose: str = "signup"):
    """Creates a hashed OTP row and sends it via email/SMS."""
    channel = _channel_for(user.email, user.phone_number)
    otp = utils.generate_otp()

    # Note: You'll need to create a VerificationCode model if you want OTP
    # For now, we'll just log it
    print(f"[DEV] {purpose} OTP for user {user.id}: {otp}")
    
    # If you have a VerificationCode model, uncomment this:
    # code = models.VerificationCode(
    #     user_id=user.id,
    #     code_hash=utils.hash_otp(otp),
    #     purpose=purpose,
    #     channel=channel,
    #     expires_at=datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES),
    # )
    # db.add(code)
    # db.commit()

    if channel == "email":
        print(f"[DEV] Would email OTP {otp} to {user.email}")
    else:
        print(f"[DEV] Would SMS OTP {otp} to {user.phone_number}")

    return channel


def _issue_token(user: models.User) -> dict:
    """Issue a JWT token for a user with their current role."""
    access_token = oauth2.create_access_token(
        data={"user_id": user.id}
    )
    
    # Build roles list (single role)
    roles = []
    roles.append({
        "role": user.role.value,
        "profile_complete": user.profile_complete,
        "verification_status": None  # You can add driver verification status if needed
    })
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "active_role": user.role.value,
        "roles": roles
    }


# ==========================================================
# 1. Registration (Simplified)
# ==========================================================

@router.post("/signup", response_model=schemas.UserOut)
def signup(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    # Check if user exists
    existing = _get_user_by_identifier(db, payload.email, payload.phone_number)
    
    if existing:
        # If user exists but is not verified, allow resend
        if not existing.is_verified:
            _send_verification(db, existing, purpose="signup")
            return existing
        
        # If user exists and is verified, return error
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email or phone already exists."
        )
    
    # Create new user
    hashed_password = utils.hash(payload.password)
    
    new_user = models.User(
        email=payload.email,
        phone_number=payload.phone_number,
        password=hashed_password,
        role=payload.role,
        is_verified=False,
        is_active=True,
        profile_complete=False
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Send verification
    _send_verification(db, new_user, purpose="signup")
    
    return new_user


@router.post("/verify-otp")
def verify_otp(
    payload: dict,  # {email: str, phone_number: str, otp: str}
    db: Session = Depends(get_db)
):
    email = payload.get("email")
    phone_number = payload.get("phone_number")
    otp = payload.get("otp")
    
    user = _get_user_by_identifier(db, email, phone_number)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Account not found."
        )
    
    # For now, accept any OTP or just verify without OTP
    # In production, verify the OTP properly
    user.is_verified = True
    db.commit()
    db.refresh(user)
    
    return _issue_token(user)


@router.post("/resend-verification")
def resend_verification(
    payload: dict,  # {email: str, phone_number: str}
    db: Session = Depends(get_db)
):
    email = payload.get("email")
    phone_number = payload.get("phone_number")
    
    user = _get_user_by_identifier(db, email, phone_number)
    if not user:
        return {"detail": "If an account exists, a new code has been sent."}
    
    _send_verification(db, user, purpose="signup")
    return {"detail": "A new verification code has been sent."}


# ==========================================================
# 2. Login (Simplified)
# ==========================================================

@router.post("/login")
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    user = _get_user_by_identifier(db, payload.email, payload.phone_number)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid email/phone or password"
        )
    
    if not utils.verify(payload.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid email/phone or password"
        )
    
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Please verify your account first."
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Your account has been deactivated."
        )
    
    return _issue_token(user)


# ==========================================================
# 3. Role management (Simplified)
# ==========================================================

@router.patch("/role", response_model=dict)
def update_role(
    payload: dict,  # {role: "passenger" or "driver"}
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user)
):
    new_role = payload.get("role")
    
    if new_role not in ["passenger", "driver"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be 'passenger' or 'driver'"
        )
    
    # Update role
    current_user.role = models.UserRoleEnum(new_role)
    current_user.update_profile_complete()
    
    db.commit()
    db.refresh(current_user)
    
    return _issue_token(current_user)


@router.get("/me", response_model=schemas.UserOut)
def get_me(
    current_user: models.User = Depends(oauth2.get_current_user)
):
    return current_user


# ==========================================================
# 4. Password reset (Simplified)
# ==========================================================

@router.post("/forgot-password")
def forgot_password(
    payload: schemas.ForgotPassword, 
    db: Session = Depends(get_db)
):
    user = _get_user_by_identifier(db, payload.email, payload.phone_number)
    if not user:
        return {"detail": "If an account exists, reset instructions have been sent."}
    
    _send_verification(db, user, purpose="password_reset")
    return {"detail": "If an account exists, reset instructions have been sent."}


@router.post("/reset-password")
def reset_password(
    payload: dict,  # {identifier: str, token_or_otp: str, new_password: str}
    db: Session = Depends(get_db)
):
    identifier = payload.get("identifier")
    token_or_otp = payload.get("token_or_otp")
    new_password = payload.get("new_password")
    
    # Determine if identifier is email or phone
    is_email = "@" in identifier if identifier else False
    
    user = _get_user_by_identifier(
        db,
        identifier if is_email else None,
        None if is_email else identifier,
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid request."
        )
    
    # For now, accept any token
    # In production, verify the token/OTP properly
    user.password = utils.hash(new_password)
    db.commit()
    
    return {"detail": "Password has been reset."}


@router.post("/logout")
def logout():
    # Stateless JWT — logout is client-side
    return {"detail": "Logged out."}