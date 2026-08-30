from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Response, status, Depends, APIRouter, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from ..database import get_db
from .. import models, schemas, utils, oauth2, email_utils
from typing import List
from sqlalchemy import or_
import re

FRONTEND_URL = "https://app.wenyfour.com.ng"

router = APIRouter(tags=["Users"])

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def format_nigerian_phone(phone: str) -> str:
    """Formats local Nigerian phone numbers to standard international
    format without '+'. Example: '09038967078' -> '2349038967078'.
    Used for matching against stored phone_number values, which may be
    saved in either local or international format historically."""
    clean_phone = phone.strip().replace(" ", "").replace("-", "")
    if clean_phone.startswith("0"):
        return f"234{clean_phone[1:]}"
    elif clean_phone.startswith("+234"):
        return clean_phone[1:]
    elif clean_phone.startswith("234"):
        return clean_phone
    return clean_phone


@router.post(
    "/users",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.UserOut
)
def create_user(
    user: schemas.UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Registers a new account. Sends an email verification link if an
    email was given, and dispatches a Kudisms SMS OTP if a phone number
    was given. User must register either an email or a phone number, but not both.
    Returns the new user object with an access token for immediate login."""
    hashed_password = utils.hash(user.password)
    user_dict = user.model_dump()
    user_dict["password"] = hashed_password

    new_user = models.User(**user_dict)
    # New accounts start incomplete and inactive until they verify
    # their contact method (email link and/or phone OTP).
    new_user.profile_complete = False
    new_user.is_active = False

    db.add(new_user)
    try:
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        # Most likely cause: email or phone_number already exists (both unique columns).
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or phone number already exists."
        )

    # --- Email verification flow ---
    if new_user.email:
        verify_token = oauth2.create_email_verification_token(new_user.id)
        verify_link = f"{FRONTEND_URL}/verify-email?token={verify_token}"
        background_tasks.add_task(
            email_utils.send_confirmation_email,
            to_email=new_user.email,
            name=new_user.full_name or "there",
            link=verify_link,
        )

    # --- SMS OTP dispatch flow (Kudisms) ---
    # Kudisms generates and tracks the OTP itself — we only store the
    # verification_id it returns, used later in /verify-otp.
    if new_user.phone_number:
        otp_result = utils.send_kudisms_otp(new_user.phone_number)
        if otp_result["success"]:
            new_user.otp_verification_id = otp_result["verification_id"]
            db.commit()
        else:
            # Registration still succeeds even if the SMS send fails —
            # the user can retry via /resend-otp. Logged for visibility.
            print(f"[OTP DISPATCH FAILED] user_id={new_user.id} error={otp_result.get('error')}")

    # Log the user in immediately on signup rather than requiring a
    # separate login call afterward.
    new_user.access_token = oauth2.create_access_token(data={"user_id": new_user.id})
    new_user.token_type = "bearer"

    return new_user


@router.post("/verify-otp", status_code=status.HTTP_200_OK)
def verify_otp(request: schemas.VerifyOTP, db: Session = Depends(get_db)):
    """Verifies the OTP the user received via SMS against Kudisms.
    On success, activates the account. Matches on either raw or
    formatted phone number since stored values may be in either form."""
    formatted_phone = format_nigerian_phone(request.phone_number)

    user = db.query(models.User).filter(
        (models.User.phone_number == request.phone_number)
        | (models.User.phone_number == formatted_phone)
    ).first()

    if not user or not user.otp_verification_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending OTP verification for this phone number."
        )

    result = utils.verify_kudisms_otp(user.otp_verification_id, request.otp)
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("msg", "Invalid or expired OTP.")
        )

    user.is_active = True
    user.otp_verification_id = None  # consumed — can't be reused
    db.commit()

    return {"message": "Phone number verified successfully."}


@router.post("/resend-otp", status_code=status.HTTP_200_OK)
def resend_otp(request: schemas.ResendOTP, db: Session = Depends(get_db)):
    """Triggers a fresh OTP send for a phone number whose previous OTP
    expired or wasn't received. Overwrites the old verification_id, so
    only the newest OTP will ever be valid."""
    formatted_phone = format_nigerian_phone(request.phone_number)

    user = db.query(models.User).filter(
        (models.User.phone_number == request.phone_number)
        | (models.User.phone_number == formatted_phone)
    ).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    otp_result = utils.send_kudisms_otp(user.phone_number)
    if not otp_result["success"]:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=otp_result.get("error", "Failed to resend OTP.")
        )

    user.otp_verification_id = otp_result["verification_id"]
    db.commit()

    return {"message": "OTP resent successfully."}


@router.get(
    "/users",
    status_code=status.HTTP_200_OK,
    response_model=List[schemas.UserOut]
)
def get_all_users(db: Session = Depends(get_db)):
    """Returns all registered users. NOTE: no admin check here currently —
    consider restricting this to admins before production, since it
    exposes every user's profile data."""
    return db.query(models.User).all()


@router.get('/users/{id}', response_model=schemas.UserOut)
def get_user(id: int, db: Session = Depends(get_db)):
    """Fetches a single user by ID. Returns 404 if not found."""
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {id} not found"
        )
    return user


@router.delete("/users/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user)
):
    """Deletes a user account by ID.
    Enforces authorization to ensure users can only delete their own account
    (or an admin can delete any account if an admin role check is added).
    Returns HTTP 204 No Content on successful deletion."""
    user_query = db.query(models.User).filter(models.User.id == id)
    user = user_query.first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {id} does not exist."
        )

    # Authorization Check: Prevent regular users from deleting other accounts
    if user.id != current_user.id and getattr(current_user, "role", None) != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform requested action."
        )

    user_query.delete(synchronize_session=False)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    """Confirms email ownership via the link sent at signup. Activates
    the account (is_active) and marks it verified (is_verified)."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired verification link"
    )
    user_id = oauth2.verify_email_verification_token(token, credentials_exception)

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise credentials_exception

    user.is_active = True
    user.is_verified = True
    db.commit()
    return {"message": "Email verified successfully."}


@router.post("/forgot-password")
def forgot_password(
    request: schemas.ForgotPassword,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Starts a password reset. Always returns the same generic message
    regardless of whether the account exists, so this endpoint can't be
    used to check which emails/phone numbers are registered."""
    generic_response = {
        "message": "If an account with that email/phone exists, a reset link has been sent."
    }

    if request.email:
        email = request.email.strip()

        if not EMAIL_REGEX.match(email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please provide a valid email address."
            )

        user = db.query(models.User).filter(models.User.email == email).first()

        if not user:
            return generic_response  # don't reveal that this email isn't registered

        reset_token = oauth2.create_reset_token(user.id)
        reset_link = f"{FRONTEND_URL}/reset-password?token={reset_token}"

        background_tasks.add_task(
            email_utils.send_password_reset_email,
            to_email=user.email,
            name=user.full_name or "there",
            link=reset_link,
        )
        return generic_response

    elif request.phone_number:
        raw_phone = request.phone_number.strip()
        formatted_phone = format_nigerian_phone(raw_phone)

        user = db.query(models.User).filter(
            (models.User.phone_number == raw_phone) | (models.User.phone_number == formatted_phone)
        ).first()

        if not user:
            return generic_response  # don't reveal that this number isn't registered

        # Reuses the same Kudisms OTP flow as registration — the user
        # verifies via /verify-otp, then the frontend should prompt for
        # a new password (a dedicated "reset via OTP" endpoint could be
        # added later if you want the OTP to directly gate a password change).
        otp_result = utils.send_kudisms_otp(user.phone_number)
        if otp_result["success"]:
            user.otp_verification_id = otp_result["verification_id"]
            db.commit()
        else:
            print(f"[FORGOT-PASSWORD OTP FAILED] user_id={user.id} error={otp_result.get('error')}")

        return generic_response

    # Shouldn't reach here — schemas.ForgotPassword's validator already
    # enforces that exactly one of email/phone_number is present.
    return generic_response


@router.post("/reset-password")
def reset_password(request: schemas.ResetPassword, db: Session = Depends(get_db)):
    """Completes a password reset using the token from forgot-password
    (email flow). Rejects invalid/expired/wrong-scope tokens."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired reset token"
    )
    user_id = oauth2.verify_reset_token(request.token, credentials_exception)
    user = db.query(models.User).filter(models.User.id == user_id).first()

    if not user:
        raise credentials_exception

    user.password = utils.hash(request.new_password)
    db.commit()
    return {"message": "Password has been reset successfully."}