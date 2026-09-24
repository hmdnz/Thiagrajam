import re
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import email_utils, models, oauth2, schemas, utils
from ..database import get_db

FRONTEND_URL = "https://app.wenyfour.com.ng"

router = APIRouter(tags=["Users"])

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def format_nigerian_phone(phone: str) -> str:
    """
    Formats local Nigerian phone numbers to standard international format 
    without '+'. Example: '09038967078' -> '2349038967078'.
    """
    clean_phone = phone.strip().replace(" ", "").replace("-", "")
    if clean_phone.startswith("0"):
        return f"234{clean_phone[1:]}"
    if clean_phone.startswith("+234"):
        return clean_phone[1:]
    if clean_phone.startswith("234"):
        return clean_phone
    return clean_phone


# ============================================================
# ENDPOINTS
# ============================================================

@router.post(
    "/users",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.UserOut,
)
def create_user(
    user: schemas.UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Registers a new user account.
    
    Business Rules:
    - Every new user starts as a passenger.
    - Phone numbers are standardized to 234 format.
    - Sends verification email or KudiSMS OTP based on provided contact info.
    """
    hashed_password = utils.hash(user.password)
    user_dict = user.model_dump()
    user_dict["password"] = hashed_password

    if user_dict.get("phone_number"):
        user_dict["phone_number"] = format_nigerian_phone(user_dict["phone_number"])

    # Force role to passenger regardless of payload
    user_dict["role"] = models.UserRoleEnum.passenger

    new_user = models.User(**user_dict)
    
    # Initial status attributes
    new_user.profile_complete = False
    new_user.is_active = False 
    new_user.is_verified = False
    new_user.nin_verified = False
    new_user.nin_verification_status = models.VerificationStatusEnum.unverified

    db.add(new_user)
    try:
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or phone number already exists.",
        )

    # Dispatch Email Verification
    if new_user.email:
        verify_token = oauth2.create_email_verification_token(new_user.id)
        verify_link = f"{FRONTEND_URL}/verify-email?token={verify_token}"
        background_tasks.add_task(
            email_utils.send_confirmation_email,
            to_email=new_user.email,
            name=new_user.full_name or "there",
            link=verify_link,
        )

    # Dispatch SMS OTP Verification
    if new_user.phone_number:
        otp_result = utils.send_kudisms_otp(new_user.phone_number)
        if otp_result.get("success"):
            new_user.otp_verification_id = otp_result.get("verification_id")
            db.commit()
        else:
            print(f"[OTP DISPATCH FAILED] user_id={new_user.id} error={otp_result.get('error')}")

    # Generate immediate login token
    new_user.access_token = oauth2.create_access_token(data={"user_id": new_user.id})
    new_user.token_type = "bearer"

    return new_user


@router.post("/verify-otp", status_code=status.HTTP_200_OK)
def verify_otp(request: schemas.VerifyOTP, db: Session = Depends(get_db)):
    """
    Verifies the OTP received via SMS.
    On success, activates the account and marks it verified.
    """
    formatted_phone = format_nigerian_phone(request.phone_number)

    user = db.query(models.User).filter(
        or_(
            models.User.phone_number == request.phone_number,
            models.User.phone_number == formatted_phone,
        )
    ).first()

    if not user or not user.otp_verification_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No pending OTP verification for this phone number.",
        )

    result = utils.verify_kudisms_otp(user.otp_verification_id, request.otp)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("msg", "Invalid or expired OTP."),
        )

    # Mark user as active and verified
    user.is_verified = True
    user.is_active = True
    user.otp_verification_id = None  # Consume OTP
    db.commit()


    # Refresh to load committed database state
    db.refresh(user)

    # Generate access token
    access_token = oauth2.create_access_token(data={"user_id": user.id})

    return {"message": "Phone number verified successfully."}


@router.post("/resend-otp", status_code=status.HTTP_200_OK)
def resend_otp(request: schemas.ResendOTP, db: Session = Depends(get_db)):
    """
    Triggers a fresh OTP send for a phone number. Overwrites old verification ID.
    """
    formatted_phone = format_nigerian_phone(request.phone_number)

    user = db.query(models.User).filter(
        or_(
            models.User.phone_number == request.phone_number,
            models.User.phone_number == formatted_phone,
        )
    ).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    otp_result = utils.send_kudisms_otp(user.phone_number)
    if not otp_result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=otp_result.get("error", "Failed to resend OTP."),
        )

    user.otp_verification_id = otp_result.get("verification_id")
    db.commit()

    return {"message": "OTP resent successfully."}


@router.get(
    "/users",
    status_code=status.HTTP_200_OK,
    response_model=List[schemas.UserOut],
)
def get_all_users(db: Session = Depends(get_db)):
    """Returns all registered users."""
    return db.query(models.User).all()


@router.get("/users/{id}", response_model=schemas.UserOut)
def get_user(id: int, db: Session = Depends(get_db)):
    """Fetches a single user by ID."""
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {id} not found",
        )
    return user


@router.delete("/users/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """Deletes a user account by ID with permissions check."""
    user_query = db.query(models.User).filter(models.User.id == id)
    user = user_query.first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {id} does not exist.",
        )

    is_admin = getattr(current_user, "is_admin", False) or getattr(current_user, "role", None) == "admin"
    if user.id != current_user.id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform requested action.",
        )

    user_query.delete(synchronize_session=False)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    """Confirms email ownership via link."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired verification link",
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
    db: Session = Depends(get_db),
):
    """Initiates password reset flow."""
    generic_response = {
        "message": "If an account with that email/phone exists, a reset link has been sent."
    }

    if request.email:
        email = request.email.strip()
        if not EMAIL_REGEX.match(email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please provide a valid email address.",
            )

        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            return generic_response

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
            or_(
                models.User.phone_number == raw_phone,
                models.User.phone_number == formatted_phone,
            )
        ).first()

        if not user:
            return generic_response

        otp_result = utils.send_kudisms_otp(user.phone_number)
        if otp_result.get("success"):
            user.otp_verification_id = otp_result.get("verification_id")
            db.commit()
        else:
            print(f"[FORGOT-PASSWORD OTP FAILED] user_id={user.id} error={otp_result.get('error')}")

        return generic_response

    return generic_response


@router.post("/reset-password")
def reset_password(request: schemas.ResetPassword, db: Session = Depends(get_db)):
    """Completes password reset using token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired reset token",
    )
    user_id = oauth2.verify_reset_token(request.token, credentials_exception)
    user = db.query(models.User).filter(models.User.id == user_id).first()

    if not user:
        raise credentials_exception

    user.password = utils.hash(request.new_password)
    db.commit()

    return {"message": "Password has been reset successfully."}