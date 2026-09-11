# from fastapi import (
#     HTTPException,
#     Response,
#     status,
#     Depends,
#     APIRouter,
#     BackgroundTasks,
# )

# from sqlalchemy.orm import Session
# from sqlalchemy.exc import IntegrityError
# from sqlalchemy import or_

# from typing import List
# import re

# from ..database import get_db
# from .. import models, schemas, utils, oauth2, email_utils


# # ---------------------------------------------------------------
# # Configuration
# # ---------------------------------------------------------------

# FRONTEND_URL = "https://app.wenyfour.com.ng"

# router = APIRouter(tags=["Users"])

# EMAIL_REGEX = re.compile(
#     r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
# )


# # ---------------------------------------------------------------
# # Nigerian Phone Number Formatting
# # ---------------------------------------------------------------

# def format_nigerian_phone(phone: str) -> str:
#     """
#     Formats Nigerian phone numbers into international format
#     without the '+' sign.

#     Examples:

#         09038967078
#         -> 2349038967078

#         +2349038967078
#         -> 2349038967078

#         2349038967078
#         -> 2349038967078

#     This also allows matching against historically stored
#     phone numbers that may exist in different formats.
#     """

#     clean_phone = (
#         phone
#         .strip()
#         .replace(" ", "")
#         .replace("-", "")
#     )

#     if clean_phone.startswith("0"):
#         return f"234{clean_phone[1:]}"

#     if clean_phone.startswith("+234"):
#         return clean_phone[1:]

#     if clean_phone.startswith("234"):
#         return clean_phone

#     return clean_phone


# # ---------------------------------------------------------------
# # CREATE USER / SIGNUP
# # ---------------------------------------------------------------

# @router.post(
#     "/users",
#     status_code=status.HTTP_201_CREATED,
#     response_model=schemas.UserOut,
# )
# def create_user(
#     user: schemas.UserCreate,
#     background_tasks: BackgroundTasks,
#     db: Session = Depends(get_db),
# ):
#     """
#     Registers a new Wenyfour account.

#     BUSINESS RULES
#     --------------

#     1. Every new account starts as a passenger.

#     2. The frontend cannot register somebody directly as a driver.

#     3. Becoming a driver is a separate application process.

#     4. A driver must later have an approved DriverProfile.

#     5. Email or phone verification activates the account.

#     6. NIN verification is separate from account verification.

#     7. Profile completion is separate from NIN verification.
#     """

#     # -----------------------------------------------------------
#     # Hash Password
#     # -----------------------------------------------------------

#     hashed_password = utils.hash(user.password)

#     # Convert Pydantic model to dictionary
#     user_dict = user.model_dump()

#     # Replace plain password with hashed password
#     user_dict["password"] = hashed_password

#     # -----------------------------------------------------------
#     # Format Phone Number
#     # -----------------------------------------------------------

#     if user_dict.get("phone_number"):
#         user_dict["phone_number"] = format_nigerian_phone(
#             user_dict["phone_number"]
#         )

#     # -----------------------------------------------------------
#     # IMPORTANT:
#     # Every new account starts as a passenger.
#     #
#     # Do NOT trust the role sent by React.
#     # -----------------------------------------------------------

#     user_dict["role"] = models.UserRoleEnum.passenger

#     # -----------------------------------------------------------
#     # Create User
#     # -----------------------------------------------------------

#     new_user = models.User(**user_dict)

#     # -----------------------------------------------------------
#     # Initial Account State
#     # -----------------------------------------------------------

#     # User has not completed their profile yet.
#     new_user.profile_complete = False

#     # Account remains inactive until email/phone verification.
#     new_user.is_active = False

#     # NIN has nothing to do with account activation.
#     new_user.nin_verified = False

#     # Explicitly start NIN verification as unverified.
#     new_user.nin_verification_status = (
#         models.VerificationStatusEnum.unverified
#     )

#     # No driver profile is created during signup.
#     #
#     # The user becomes a driver only after:
#     #
#     #   1. common profile is complete
#     #   2. driver information is submitted
#     #   3. licence is verified by admin
#     #
#     # Therefore we deliberately do NOT create DriverProfile here.

#     db.add(new_user)

#     try:
#         db.commit()
#         db.refresh(new_user)

#     except IntegrityError:
#         db.rollback()

#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Email or phone number already exists.",
#         )

#     # -----------------------------------------------------------
#     # EMAIL VERIFICATION
#     # -----------------------------------------------------------

#     if new_user.email:

#         verify_token = oauth2.create_email_verification_token(
#             new_user.id
#         )

#         verify_link = (
#             f"{FRONTEND_URL}/verify-email"
#             f"?token={verify_token}"
#         )

#         background_tasks.add_task(
#             email_utils.send_confirmation_email,
#             to_email=new_user.email,
#             name=new_user.full_name or "there",
#             link=verify_link,
#         )

#     # -----------------------------------------------------------
#     # SMS OTP VERIFICATION
#     # -----------------------------------------------------------

#     if new_user.phone_number:

#         otp_result = utils.send_kudisms_otp(
#             new_user.phone_number
#         )

#         if otp_result["success"]:

#             new_user.otp_verification_id = (
#                 otp_result["verification_id"]
#             )

#             db.commit()

#         else:

#             print(
#                 "[OTP DISPATCH FAILED] "
#                 f"user_id={new_user.id} "
#                 f"error={otp_result.get('error')}"
#             )

#     # -----------------------------------------------------------
#     # Immediate Access Token
#     # -----------------------------------------------------------

#     # The token can be returned immediately.
#     #
#     # However, protected endpoints should still respect
#     # current_user.is_active where appropriate.
#     #
#     # Account activation remains controlled by email/phone
#     # verification.

#     new_user.access_token = oauth2.create_access_token(
#         data={
#             "user_id": new_user.id
#         }
#     )

#     new_user.token_type = "bearer"

#     return new_user


# # ---------------------------------------------------------------
# # VERIFY PHONE OTP
# # ---------------------------------------------------------------

# @router.post(
#     "/verify-otp",
#     status_code=status.HTTP_200_OK,
# )
# def verify_otp(
#     request: schemas.VerifyOTP,
#     db: Session = Depends(get_db),
# ):
#     """
#     Verifies a phone number using the Kudisms OTP.

#     Successful verification activates the account.

#     This does NOT:

#         - verify NIN
#         - make the user a driver
#         - complete the profile

#     Those are separate processes.
#     """

#     formatted_phone = format_nigerian_phone(
#         request.phone_number
#     )

#     user = (
#         db.query(models.User)
#         .filter(
#             or_(
#                 models.User.phone_number
#                 == request.phone_number,

#                 models.User.phone_number
#                 == formatted_phone,
#             )
#         )
#         .first()
#     )

#     if not user or not user.otp_verification_id:

#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="No pending OTP verification for this phone number.",
#         )

#     # -----------------------------------------------------------
#     # Verify OTP
#     # -----------------------------------------------------------

#     result = utils.verify_kudisms_otp(
#         user.otp_verification_id,
#         request.otp,
#     )

#     if not result["success"]:

#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail=result.get(
#                 "msg",
#                 "Invalid or expired OTP.",
#             ),
#         )

#     # -----------------------------------------------------------
#     # Activate Account
#     # -----------------------------------------------------------

#     user.is_active = True

#     # OTP has now been consumed.
#     user.otp_verification_id = None

#     # IMPORTANT:
#     #
#     # Do NOT modify:
#     #
#     #   user.role
#     #   user.nin_verified
#     #   user.nin_verification_status
#     #
#     # Phone verification is separate from those systems.

#     db.commit()

#     return {
#         "message": "Phone number verified successfully."
#     }


# # ---------------------------------------------------------------
# # RESEND OTP
# # ---------------------------------------------------------------

# @router.post(
#     "/resend-otp",
#     status_code=status.HTTP_200_OK,
# )
# def resend_otp(
#     request: schemas.ResendOTP,
#     db: Session = Depends(get_db),
# ):
#     """
#     Sends a fresh OTP to the user's phone number.

#     The previous OTP verification ID is replaced.
#     """

#     formatted_phone = format_nigerian_phone(
#         request.phone_number
#     )

#     user = (
#         db.query(models.User)
#         .filter(
#             or_(
#                 models.User.phone_number
#                 == request.phone_number,

#                 models.User.phone_number
#                 == formatted_phone,
#             )
#         )
#         .first()
#     )

#     if not user:

#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="User not found.",
#         )

#     # -----------------------------------------------------------
#     # Send New OTP
#     # -----------------------------------------------------------

#     otp_result = utils.send_kudisms_otp(
#         user.phone_number
#     )

#     if not otp_result["success"]:

#         raise HTTPException(
#             status_code=status.HTTP_502_BAD_GATEWAY,
#             detail=otp_result.get(
#                 "error",
#                 "Failed to resend OTP.",
#             ),
#         )

#     user.otp_verification_id = (
#         otp_result["verification_id"]
#     )

#     db.commit()

#     return {
#         "message": "OTP resent successfully."
#     }


# # ---------------------------------------------------------------
# # GET ALL USERS
# # ---------------------------------------------------------------

# @router.get(
#     "/users",
#     status_code=status.HTTP_200_OK,
#     response_model=List[schemas.UserOut],
# )
# def get_all_users(
#     db: Session = Depends(get_db),
# ):
#     """
#     Returns all registered users.

#     NOTE:
#     For production, this endpoint should eventually be protected
#     so that only administrators can access the full user list.
#     """

#     return (
#         db.query(models.User)
#         .all()
#     )


# # ---------------------------------------------------------------
# # GET SINGLE USER
# # ---------------------------------------------------------------

# @router.get(
#     "/users/{id}",
#     response_model=schemas.UserOut,
# )
# def get_user(
#     id: int,
#     db: Session = Depends(get_db),
# ):
#     """
#     Fetches a single user by ID.
#     """

#     user = (
#         db.query(models.User)
#         .filter(models.User.id == id)
#         .first()
#     )

#     if not user:

#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail=f"User with ID {id} not found",
#         )

#     return user


# # ---------------------------------------------------------------
# # DELETE USER
# # ---------------------------------------------------------------

# @router.delete(
#     "/users/{id}",
#     status_code=status.HTTP_204_NO_CONTENT,
# )
# def delete_user(
#     id: int,
#     db: Session = Depends(get_db),
#     current_user: models.User = Depends(
#         oauth2.get_current_user
#     ),
# ):
#     """
#     Deletes a user account.

#     A user can delete their own account.

#     An administrator can delete another user's account.
#     """

#     user_query = (
#         db.query(models.User)
#         .filter(models.User.id == id)
#     )

#     user = user_query.first()

#     if not user:

#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail=f"User with ID {id} does not exist.",
#         )

#     # -----------------------------------------------------------
#     # Authorization
#     # -----------------------------------------------------------

#     if (
#         user.id != current_user.id
#         and not current_user.is_admin
#     ):

#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Not authorized to perform requested action.",
#         )

#     # -----------------------------------------------------------
#     # Delete
#     # -----------------------------------------------------------

#     user_query.delete(
#         synchronize_session=False
#     )

#     db.commit()

#     return Response(
#         status_code=status.HTTP_204_NO_CONTENT
#     )


# # ---------------------------------------------------------------
# # VERIFY EMAIL
# # ---------------------------------------------------------------

# @router.post("/verify-email")
# def verify_email(
#     token: str,
#     db: Session = Depends(get_db),
# ):
#     """
#     Confirms email ownership using the verification token.

#     Successful verification activates the account.

#     This does NOT:

#         - verify NIN
#         - approve driver status
#         - complete the profile
#     """

#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Invalid or expired verification link",
#     )

#     user_id = oauth2.verify_email_verification_token(
#         token,
#         credentials_exception,
#     )

#     user = (
#         db.query(models.User)
#         .filter(models.User.id == user_id)
#         .first()
#     )

#     if not user:
#         raise credentials_exception

#     # -----------------------------------------------------------
#     # Activate Account
#     # -----------------------------------------------------------

#     user.is_active = True

#     db.commit()

#     return {
#         "message": "Email verified successfully."
#     }


# # ---------------------------------------------------------------
# # FORGOT PASSWORD
# # ---------------------------------------------------------------

# @router.post("/forgot-password")
# def forgot_password(
#     request: schemas.ForgotPassword,
#     background_tasks: BackgroundTasks,
#     db: Session = Depends(get_db),
# ):
#     """
#     Starts the password reset process.

#     Supports:

#         - email
#         - phone number
#     """

#     generic_response = {
#         "message": (
#             "If an account with that email/phone exists, "
#             "a reset link has been sent."
#         )
#     }

#     # -----------------------------------------------------------
#     # EMAIL PASSWORD RESET
#     # -----------------------------------------------------------

#     if request.email:

#         email = request.email.strip()

#         if not EMAIL_REGEX.match(email):

#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Please provide a valid email address.",
#             )

#         user = (
#             db.query(models.User)
#             .filter(models.User.email == email)
#             .first()
#         )

#         if not user:
#             return generic_response

#         reset_token = oauth2.create_reset_token(
#             user.id
#         )

#         reset_link = (
#             f"{FRONTEND_URL}/reset-password"
#             f"?token={reset_token}"
#         )

#         background_tasks.add_task(
#             email_utils.send_password_reset_email,
#             to_email=user.email,
#             name=user.full_name or "there",
#             link=reset_link,
#         )

#         return generic_response

#     # -----------------------------------------------------------
#     # PHONE PASSWORD RESET
#     # -----------------------------------------------------------

#     elif request.phone_number:

#         raw_phone = (
#             request.phone_number.strip()
#         )

#         formatted_phone = format_nigerian_phone(
#             raw_phone
#         )

#         user = (
#             db.query(models.User)
#             .filter(
#                 or_(
#                     models.User.phone_number
#                     == raw_phone,

#                     models.User.phone_number
#                     == formatted_phone,
#                 )
#             )
#             .first()
#         )

#         if not user:
#             return generic_response

#         otp_result = utils.send_kudisms_otp(
#             user.phone_number
#         )

#         if otp_result["success"]:

#             user.otp_verification_id = (
#                 otp_result["verification_id"]
#             )

#             db.commit()

#         else:

#             print(
#                 "[FORGOT-PASSWORD OTP FAILED] "
#                 f"user_id={user.id} "
#                 f"error={otp_result.get('error')}"
#             )

#         return generic_response

#     return generic_response


# # ---------------------------------------------------------------
# # RESET PASSWORD
# # ---------------------------------------------------------------

# @router.post("/reset-password")
# def reset_password(
#     request: schemas.ResetPassword,
#     db: Session = Depends(get_db),
# ):
#     """
#     Resets the user's password using a valid reset token.
#     """

#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Invalid or expired reset token",
#     )

#     user_id = oauth2.verify_reset_token(
#         request.token,
#         credentials_exception,
#     )

#     user = (
#         db.query(models.User)
#         .filter(models.User.id == user_id)
#         .first()
#     )

#     if not user:
#         raise credentials_exception

#     # -----------------------------------------------------------
#     # Update Password
#     # -----------------------------------------------------------

#     user.password = utils.hash(
#         request.new_password
#     )

#     db.commit()

#     return {
#         "message": "Password has been reset successfully."
#     }


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

    if user_dict.get("phone_number"):
        user_dict["phone_number"] = format_nigerian_phone(user_dict["phone_number"])

    new_user = models.User(**user_dict)
    # New accounts start incomplete and inactive until they verify
    # their contact method (email link and/or phone OTP).
    new_user.profile_complete = False
    new_user.is_active = False 
    new_user.is_verified = False

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
    On success, activates the account and marks it verified.
    Matches on either raw or formatted phone number."""
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

    # Mark user as verified and active upon successful OTP check
    user.is_verified = False  # 
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
    """Returns all registered users."""
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
    """Deletes a user account by ID. Enforces authorization."""
    user_query = db.query(models.User).filter(models.User.id == id)
    user = user_query.first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {id} does not exist."
        )

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
    """Confirms email ownership via the link sent at signup."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired verification link"
    )
    user_id = oauth2.verify_email_verification_token(token, credentials_exception)

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise credentials_exception

    user.is_active = True
    user.is_verified = False
    db.commit()
    return {"message": "Email verified successfully."}


@router.post("/forgot-password")
def forgot_password(
    request: schemas.ForgotPassword,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Starts a password reset."""
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
            (models.User.phone_number == raw_phone) | (models.User.phone_number == formatted_phone)
        ).first()

        if not user:
            return generic_response

        otp_result = utils.send_kudisms_otp(user.phone_number)
        if otp_result["success"]:
            user.otp_verification_id = otp_result["verification_id"]
            db.commit()
        else:
            print(f"[FORGOT-PASSWORD OTP FAILED] user_id={user.id} error={otp_result.get('error')}")

        return generic_response

    return generic_response


@router.post("/reset-password")
def reset_password(request: schemas.ResetPassword, db: Session = Depends(get_db)):
    """Completes a password reset using the token from forgot-password."""
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
