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
    """Creates a hashed OTP row and (TODO) sends it via email/SMS.

    You already have Zoho SMTP sending (for the confirmation/reset emails)
    and Termii SMS wired up elsewhere in the project (see test_sms.py) —
    plug those senders in here instead of the print() placeholders. This
    function only owns the OTP lifecycle (generate, hash, store, expire).
    """
    channel = _channel_for(user.email, user.phone_number)
    otp = utils.generate_otp()

    code = models.VerificationCode(
        user_id=user.id,
        code_hash=utils.hash_otp(otp),
        purpose=purpose,
        channel=channel,
        expires_at=datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES),
    )
    db.add(code)
    db.commit()

    if channel == "email":
        # TODO: replace with your Zoho SMTP sender, e.g.
        # send_email(to=user.email, template="otp_or_verify_link.html", otp=otp)
        print(f"[DEV] Would email OTP {otp} to {user.email}")
    else:
        # TODO: replace with your Termii sender, e.g.
        # send_sms_otp(phone=user.phone_number, otp=otp)
        print(f"[DEV] Would SMS OTP {otp} to {user.phone_number}")

    return channel


def _issue_token(user: models.User, active_role: str, roles: list[models.UserRole]) -> schemas.TokenResponse:
    access_token = oauth2.create_access_token(
        data={"user_id": user.id, "active_role": active_role}
    )
    roles_out = []
    for r in roles:
        verification_status = None
        if r.role == "driver" and user.driver_profile:
            verification_status = user.driver_profile.verification_status
        roles_out.append(
            schemas.UserRoleOut(
                role=r.role,
                profile_complete=r.profile_complete,
                verification_status=verification_status,
            )
        )
    return schemas.TokenResponse(
        access_token=access_token,
        user_id=user.id,
        active_role=active_role,
        roles=roles_out,
    )


# ==========================================================
# 1. Registration
# ==========================================================

@router.post("/signup", response_model=schemas.SignupResponse)
def signup(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = _get_user_by_identifier(db, payload.email, payload.phone_number)

    if existing:
        has_role = any(r.role == payload.role for r in existing.roles)

        if has_role and existing.is_verified:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An account with this {'role' if has_role else 'identifier'} already exists.",
            )

        if has_role and not existing.is_verified:
            # Unverified retry — just resend instead of erroring.
            channel = _send_verification(db, existing, purpose="signup")
            return schemas.SignupResponse(verification_method=channel)

        # Identifier exists but lacks this role — "register as anyone":
        # attach a new role to the existing account, same login.
        db.add(models.UserRole(user_id=existing.id, role=payload.role))
        if payload.role == "driver" and not existing.driver_profile:
            db.add(models.Driver(user_id=existing.id))
        db.commit()
        channel = _send_verification(db, existing, purpose="signup")
        return schemas.SignupResponse(verification_method=channel)

    # Brand new account
    user = models.User(
        email=payload.email,
        phone_number=payload.phone_number,
        password_hash=utils.hash(payload.password),
        is_verified=False,
    )
    db.add(user)
    db.flush()  # get user.id without committing yet

    db.add(models.UserRole(user_id=user.id, role=payload.role))
    if payload.role == "driver":
        db.add(models.Driver(user_id=user.id))
    db.commit()
    db.refresh(user)

    channel = _send_verification(db, user, purpose="signup")
    return schemas.SignupResponse(verification_method=channel)


@router.post("/verify-otp", response_model=schemas.TokenResponse)
def verify_otp(payload: schemas.VerifyOtpRequest, db: Session = Depends(get_db)):
    user = _get_user_by_identifier(db, payload.email, payload.phone_number)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    code_row = (
        db.query(models.VerificationCode)
        .filter(
            models.VerificationCode.user_id == user.id,
            models.VerificationCode.purpose == "signup",
            models.VerificationCode.used.is_(False),
        )
        .order_by(models.VerificationCode.created_at.desc())
        .first()
    )

    if (
        not code_row
        or code_row.expires_at < datetime.utcnow()
        or not utils.verify_otp(payload.otp, code_row.code_hash)
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP.")

    code_row.used = True
    user.is_verified = True
    db.commit()
    db.refresh(user)

    active_role = user.roles[0].role if user.roles else "passenger"
    return _issue_token(user, active_role, user.roles)


@router.post("/resend-verification")
def resend_verification(payload: schemas.ResendVerificationRequest, db: Session = Depends(get_db)):
    user = _get_user_by_identifier(db, payload.email, payload.phone_number)
    if not user:
        # Don't leak whether the account exists.
        return {"detail": "If an account exists, a new code has been sent."}

    recent = (
        db.query(models.VerificationCode)
        .filter(models.VerificationCode.user_id == user.id)
        .order_by(models.VerificationCode.created_at.desc())
        .first()
    )
    now = datetime.utcnow()
    if recent and (now - recent.created_at.replace(tzinfo=None)) < timedelta(seconds=RESEND_COOLDOWN_SECONDS):
        raise HTTPException(status_code=429, detail="Please wait before requesting another code.")

    one_hour_ago = now - timedelta(hours=1)
    recent_count = (
        db.query(models.VerificationCode)
        .filter(models.VerificationCode.user_id == user.id, models.VerificationCode.created_at >= one_hour_ago)
        .count()
    )
    if recent_count >= RESEND_MAX_PER_HOUR:
        raise HTTPException(status_code=429, detail="Too many resend attempts. Try again later.")

    channel = _send_verification(db, user, purpose="signup")
    return {"verification_method": channel}


# ==========================================================
# 2. Login
# ==========================================================

@router.post("/login", response_model=schemas.TokenResponse)
def login(payload: schemas.UserLogin, db: Session = Depends(get_db)):
    user = _get_user_by_identifier(db, payload.email, payload.phone_number)
    if not user or not utils.verify(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email/phone or password")

    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Please verify your account first.")

    role_row = next((r for r in user.roles if r.role == payload.role), None)
    if not role_row:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No {payload.role} account found — sign up as a {payload.role} first.",
        )

    # Driver role is still allowed to log in even if verification is
    # pending — the frontend just shows a "review pending" banner.
    return _issue_token(user, payload.role, user.roles)


# ==========================================================
# 3. Role management
# ==========================================================

@router.post("/roles", response_model=schemas.TokenResponse)
def add_role(
    payload: schemas.AddRoleRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    has_role = any(r.role == payload.role for r in current_user.roles)
    if not has_role:
        db.add(models.UserRole(user_id=current_user.id, role=payload.role))
        if payload.role == "driver" and not current_user.driver_profile:
            db.add(models.Driver(user_id=current_user.id))
        db.commit()
        db.refresh(current_user)

    return _issue_token(current_user, payload.role, current_user.roles)


@router.post("/switch-role", response_model=schemas.TokenResponse)
def switch_role(
    payload: schemas.SwitchRoleRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    has_role = any(r.role == payload.role for r in current_user.roles)
    if not has_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You don't have a {payload.role} role yet — add it first via POST /auth/roles.",
        )
    return _issue_token(current_user, payload.role, current_user.roles)


@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(oauth2.get_current_user)):
    roles_out = []
    for r in current_user.roles:
        verification_status = None
        if r.role == "driver" and current_user.driver_profile:
            verification_status = current_user.driver_profile.verification_status
        roles_out.append(
            schemas.UserRoleOut(role=r.role, profile_complete=r.profile_complete, verification_status=verification_status)
        )
    out = schemas.UserOut.model_validate(current_user)
    out.roles = roles_out
    return out


# ==========================================================
# 4. Password reset
# ==========================================================

@router.post("/forgot-password")
def forgot_password(payload: schemas.ForgotPassword, db: Session = Depends(get_db)):
    user = _get_user_by_identifier(db, payload.email, payload.phone_number)
    if not user:
        return {"detail": "If an account exists, reset instructions have been sent."}
    _send_verification(db, user, purpose="password_reset")
    return {"detail": "If an account exists, reset instructions have been sent."}


@router.post("/reset-password")
def reset_password(payload: schemas.ResetPassword, db: Session = Depends(get_db)):
    # `identifier` may be an email or a phone number — figure out which.
    is_email = "@" in payload.identifier
    user = _get_user_by_identifier(
        db,
        payload.identifier if is_email else None,
        None if is_email else payload.identifier,
    )
    if not user:
        raise HTTPException(status_code=400, detail="Invalid request.")

    code_row = (
        db.query(models.VerificationCode)
        .filter(
            models.VerificationCode.user_id == user.id,
            models.VerificationCode.purpose == "password_reset",
            models.VerificationCode.used.is_(False),
        )
        .order_by(models.VerificationCode.created_at.desc())
        .first()
    )
    if (
        not code_row
        or code_row.expires_at < datetime.utcnow()
        or not utils.verify_otp(payload.token_or_otp, code_row.code_hash)
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired code.")

    code_row.used = True
    user.password_hash = utils.hash(payload.new_password)
    db.commit()
    return {"detail": "Password has been reset."}


@router.post("/logout")
def logout():
    # Stateless JWT — logout is a client-side token clear. If you add
    # refresh tokens or a blacklist later, this is where you'd revoke them.
    return {"detail": "Logged out."}
