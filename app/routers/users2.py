"""
app/routers/users.py

API Endpoints for User management, Authentication, Profile Updates, 
and Driver Profile sync.
"""

import re
from typing import List
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import email_utils, models, oauth2, schemas, utils
from app.database import get_db

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
# AUTH & ACCOUNT MANAGEMENT
# ============================================================

@router.post(
    "/users",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.UserCreateOut,
)
def create_user(
    user: schemas.UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Registers a new user account.
    """
    hashed_password = utils.hash(user.password)

    user_dict = user.model_dump(exclude_unset=True)
    user_dict["password"] = hashed_password
    user_dict.pop("profile_complete", None)

    for key in ["email", "phone_number", "nin"]:
        if key in user_dict and isinstance(user_dict[key], str) and not user_dict[key].strip():
            user_dict[key] = None

    if user_dict.get("phone_number"):
        user_dict["phone_number"] = format_nigerian_phone(user_dict["phone_number"])

    user_dict["role"] = models.UserRoleEnum.passenger

    new_user = models.User(**user_dict)
    
    new_user.is_active = False 
    new_user.is_verified = False
    new_user.nin_verified = False
    new_user.nin_verification_status = models.VerificationStatusEnum.unverified

    db.add(new_user)
    try:
        db.commit()
        db.refresh(new_user)
    except IntegrityError as e:
        db.rollback()
        print(f"\n[DB INTEGRITY ERROR DETAIL]: {e.orig}\n")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email, phone number, or unique identifier already exists.",
        )

    if new_user.email:
        verify_token = oauth2.create_email_verification_token(str(new_user.id))
        verify_link = f"{FRONTEND_URL}/verify-email?token={verify_token}"
        background_tasks.add_task(
            email_utils.send_confirmation_email,
            to_email=new_user.email,
            name=new_user.full_name or "there",
            link=verify_link,
        )

    if new_user.phone_number:
        otp_result = utils.send_kudisms_otp(new_user.phone_number)
        if otp_result.get("success"):
            new_user.otp_verification_id = otp_result.get("verification_id")
            db.commit()
        else:
            print(f"[OTP DISPATCH FAILED] user_id={new_user.id} error={otp_result.get('error')}")

    new_user.access_token = oauth2.create_access_token(data={"user_id": str(new_user.id)})
    new_user.token_type = "bearer"

    return new_user


@router.post("/verify-otp", status_code=status.HTTP_200_OK)
def verify_otp(request: schemas.VerifyOTP, db: Session = Depends(get_db)):
    """Verifies SMS OTP, activates account, and returns access token."""
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

    user.is_verified = True
    user.is_active = True
    user.otp_verification_id = None
    db.commit()
    db.refresh(user)

    access_token = oauth2.create_access_token(data={"user_id": str(user.id)})

    return {"message": "Phone number verified successfully.", "access_token": access_token}


@router.post("/resend-otp", status_code=status.HTTP_200_OK)
def resend_otp(request: schemas.ResendOTP, db: Session = Depends(get_db)):
    """Triggers a fresh OTP send for a phone number."""
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

        reset_token = oauth2.create_reset_token(str(user.id))
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
        detail="Invalid or expired password reset token.",
    )
    
    user_id = oauth2.verify_reset_token(request.token, credentials_exception)
    user = db.query(models.User).filter(models.User.id == user_id).first()

    if not user:
        raise credentials_exception

    user.password = utils.hash(request.new_password)
    db.commit()

    return {"message": "Password updated successfully."}


@router.post("/change-password")
def change_password(
    password_data: schemas.ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """Allows an authenticated user to change their password."""
    if not utils.verify(password_data.current_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password.",
        )

    current_user.password = utils.hash(password_data.new_password)
    db.commit()

    return {"message": "Password changed successfully."}


# ============================================================
# PROFILE OPERATIONS
# ============================================================

@router.get("/profile/me", response_model=schemas.UserProfileOut)
def get_current_user_profile(
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """Fetches full profile information for the currently authenticated user."""
    return current_user


@router.put("/profile/me", response_model=schemas.UserProfileUpdate)
def update_profile(
    profile_data: schemas.ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """Updates profile attributes and syncs user & driver preferences safely."""
    update_dict = profile_data.model_dump(exclude_unset=True)

    # 1. Update User level attributes
    user_fields = [
        "full_name", "address", "date_of_birth", "gender", "phone_number",
        "next_of_kin_name", "next_of_kin_relationship", "emergency_contact",
        "blood_group", "health_conditions", "nin"
    ]
    for field in user_fields:
        if field in update_dict:
            setattr(current_user, field, update_dict[field])

    # 2. Sync User level preference fields
    if "chattiness" in update_dict:
        current_user.chattiness = update_dict["chattiness"]
    if "music" in update_dict:
        current_user.music_preference = update_dict["music"]
    if "smoking" in update_dict:
        current_user.smoking_preference = update_dict["smoking"]
    if "pets" in update_dict:
        current_user.pets_preference = update_dict["pets"]

    # 3. Sync DriverProfile preference fields if a driver profile exists
    if current_user.driver_profile:
        driver = current_user.driver_profile
        if "about_me" in update_dict:
            driver.about_me = update_dict["about_me"]
        if "chattiness" in update_dict:
            driver.chattiness = update_dict["chattiness"]
        if "music" in update_dict:
            driver.music = update_dict["music"]
        if "smoking" in update_dict:
            driver.smoking = update_dict["smoking"]
        if "pets" in update_dict:
            driver.pets = update_dict["pets"]

    db.commit()
    db.refresh(current_user)
    return current_user


# ============================================================
# DRIVER SPECIFIC ENDPOINTS
# ============================================================

@router.put("/driver/preferences", response_model=schemas.DriverPreferencesResponse)
def update_driver_preferences(
    preferences: schemas.DriverProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """Dedicated endpoint to update driver preferences."""
    driver = current_user.driver_profile
    if not driver:
        driver = models.DriverProfile(user_id=current_user.id)
        db.add(driver)

    update_dict = preferences.model_dump(exclude_unset=True)

    if "chattiness" in update_dict:
        driver.chattiness = update_dict["chattiness"]
        current_user.chattiness = update_dict["chattiness"]
    if "music" in update_dict:
        driver.music = update_dict["music"]
        current_user.music_preference = update_dict["music"]
    if "smoking" in update_dict:
        driver.smoking = update_dict["smoking"]
        current_user.smoking_preference = update_dict["smoking"]
    if "pets" in update_dict:
        driver.pets = update_dict["pets"]
        current_user.pets_preference = update_dict["pets"]
    if "license_number" in update_dict:
        driver.license_number = update_dict["license_number"]
    if "license_expiry_date" in update_dict:
        driver.license_expiry_date = update_dict["license_expiry_date"]
    if "about_me" in update_dict:
        driver.about_me = update_dict["about_me"]

    db.commit()
    db.refresh(driver)
    return driver


# ============================================================
# GENERAL USER CRUD
# ============================================================

@router.get(
    "/users",
    status_code=status.HTTP_200_OK,
    response_model=List[schemas.UserOut],
)
def get_all_users(db: Session = Depends(get_db)):
    """Returns all registered users."""
    return db.query(models.User).all()


@router.get("/users/{id}", response_model=schemas.UserOut)
def get_user(id: UUID, db: Session = Depends(get_db)):
    """Fetches a single user by UUID."""
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {id} not found",
        )
    return user


@router.delete("/users/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """Deletes a user account by UUID with permissions check."""
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