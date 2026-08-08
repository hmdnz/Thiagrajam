# from fastapi import HTTPException, Response, status,Depends,APIRouter
# from .. import models, schemas, utils, oauth2 
# # Import classes used for error handling and responses


# from sqlalchemy.orm import Session

# from sqlalchemy.exc import IntegrityError

# from ..database import get_db

# from typing import List

# from sqlalchemy import or_ 

# from fastapi import BackgroundTasks
# from .. import email_utils


# FRONTEND_URL = "https://app.wenyfour.com"  # your actual frontend base URL


# router = APIRouter(
#     tags=["Users"]
# )  


# @router.post(
#     "/users",
#     status_code=status.HTTP_201_CREATED,
#     response_model=schemas.UserOut
# )
# def create_user(
#     user: schemas.UserCreate,
#     db: Session = Depends(get_db)
# ):
#     ## Hash the password before storing it in the database
    
#     hashed_password = utils.hash(user.password)
#     user.password = hashed_password
    

#     new_user = models.User(**user.model_dump())

#     db.add(new_user)

#     try:
#         db.commit()
#         db.refresh(new_user)

#     except IntegrityError as e:
#          db.rollback()
#          raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Email or phone number already exists."
#             )
    

#     return new_user

# @router.get(
#     "/users",
#     status_code=status.HTTP_200_OK,
#     response_model=List[schemas.UserOut]   # <-- new route
# )
# def get_all_users(db: Session = Depends(get_db)):
#     """Returns all registered users."""
#     users = db.query(models.User).all()
#     return users



# @router.get('/users/{id}', response_model=schemas.UserOut)
# def get_user(id: int, db: Session = Depends(get_db)):

#     user = db.query(models.User).filter(models.User.id == id).first()

#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail=f"User with ID {id} not found"
#         )

#     return user 


# @router.post("/forgot-password")
# def forgot_password(request: schemas.ForgotPassword, db: Session = Depends(get_db)):

#     user = db.query(models.User).filter(
#         or_(
#             models.User.email == request.email,
#             models.User.phone_number == request.phone_number
#         )
#     ).first()

#     # Same response whether the account exists or not — prevents this
#     # endpoint being used to check which emails/numbers are registered.
#     generic_response = {
#         "message": "If an account with that email/phone exists, a reset link has been sent."
#     }

#     if not user:
#         return generic_response

#     reset_token = oauth2.create_reset_token(user.id)
#     _send_reset_token(user, reset_token)  # stub — still prints to console

#     # DEV ONLY — remove or gate behind an environment flag before production,
#     # since returning the token here bypasses the whole point of "forgot password".
#     generic_response["reset_token"] = reset_token

#     return generic_response


# def _send_reset_token(user: models.User, token: str):
#     """Placeholder — swap for a real email/SMS provider when ready.
#     Logs to console for local testing."""
#     print(f"[DEV] Password reset token for user {user.id}: {token}")


# @router.post("/reset-password")
# def reset_password(request: schemas.ResetPassword, db: Session = Depends(get_db)):

#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Invalid or expired reset token"
#     )

#     user_id = oauth2.verify_reset_token(request.token, credentials_exception)
#     user = db.query(models.User).filter(models.User.id == user_id).first()

#     if not user:
#         raise credentials_exception

#     user.password = utils.hash(request.new_password)
#     db.commit()

#     return {"message": "Password has been reset successfully."}

# @router.post(
#     "/users",
#     status_code=status.HTTP_201_CREATED,
#     response_model=schemas.UserOut
# )
# def create_user(
#     user: schemas.UserCreate,
#     background_tasks: BackgroundTasks,
#     db: Session = Depends(get_db)
# ):
#     hashed_password = utils.hash(user.password)
#     user.password = hashed_password

#     new_user = models.User(**user.model_dump())
#     db.add(new_user)

#     try:
#         db.commit()
#         db.refresh(new_user)
#     except IntegrityError:
#         db.rollback()
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Email or phone number already exists."
#         )

#     if new_user.email:
#         verify_token = oauth2.create_email_verification_token(new_user.id)
#         verify_link = f"{FRONTEND_URL}/verify-email?token={verify_token}"
#         background_tasks.add_task(
#             email_utils.send_confirmation_email,
#             to_email=new_user.email,
#             name=new_user.full_name or "there",
#             link=verify_link,
#         )

#     return new_user


# @router.get("/verify-email")
# def verify_email(token: str, db: Session = Depends(get_db)):
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Invalid or expired verification link"
#     )
#     user_id = oauth2.verify_email_verification_token(token, credentials_exception)

#     user = db.query(models.User).filter(models.User.id == user_id).first()
#     if not user:
#         raise credentials_exception

#     user.is_active = True
#     db.commit()

#     return {"message": "Email verified successfully."}


# @router.post("/forgot-password")
# def forgot_password(
#     request: schemas.ForgotPassword,
#     background_tasks: BackgroundTasks,
#     db: Session = Depends(get_db)
# ):
#     user = db.query(models.User).filter(
#         or_(
#             models.User.email == request.email,
#             models.User.phone_number == request.phone_number
#         )
#     ).first()

#     generic_response = {
#         "message": "If an account with that email/phone exists, a reset link has been sent."
#     }

#     if not user:
#         return generic_response

#     reset_token = oauth2.create_reset_token(user.id)
#     reset_link = f"{FRONTEND_URL}/reset-password?token={reset_token}"

#     if user.email:
#         background_tasks.add_task(
#             email_utils.send_password_reset_email,
#             to_email=user.email,
#             name=user.full_name or "there",
#             link=reset_link,
#         )
#     else:
#         _send_reset_token(user, reset_token)  # console/SMS fallback for phone-only accounts

#     return generic_response

from fastapi import HTTPException, Response, status, Depends, APIRouter, BackgroundTasks
from .. import models, schemas, utils, oauth2, email_utils
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from ..database import get_db
from typing import List
from sqlalchemy import or_
import re

FRONTEND_URL = "https://app.wenyfour.com"


router = APIRouter(tags=["Users"])

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def _looks_like_email(value: str) -> bool:
    # crude heuristic: contains letters and no digits-only pattern typical of phone numbers
    return "@" in value

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
    hashed_password = utils.hash(user.password)
    user.password = hashed_password

    new_user = models.User(**user.model_dump())
    db.add(new_user)

    try:
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or phone number already exists."
        )

    if new_user.email:
        verify_token = oauth2.create_email_verification_token(new_user.id)
        verify_link = f"{FRONTEND_URL}/verify-email?token={verify_token}"
        background_tasks.add_task(
            email_utils.send_confirmation_email,
            to_email=new_user.email,
            name=new_user.full_name or "there",
            link=verify_link,
        )

    return new_user


@router.get(
    "/users",
    status_code=status.HTTP_200_OK,
    response_model=List[schemas.UserOut]
)
def get_all_users(db: Session = Depends(get_db)):
    return db.query(models.User).all()


@router.get('/users/{id}', response_model=schemas.UserOut)
def get_user(id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {id} not found"
        )
    return user


@router.post("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired verification link"
    )
    user_id = oauth2.verify_email_verification_token(token, credentials_exception)

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise credentials_exception

    user.is_active = True
    db.commit()
    return {"message": "Email verified successfully."}


# @router.post("/forgot-password")
# def forgot_password(
#     request: schemas.ForgotPassword,
#     background_tasks: BackgroundTasks,
#     db: Session = Depends(get_db)
# ):
#     user = db.query(models.User).filter(
#         or_(
#             models.User.email == request.email,
#             models.User.phone_number == request.phone_number
#         )
#     ).first()

#     generic_response = {
#         "message": "If an account with that email/phone exists, a reset link has been sent."
#     }

#     if not user:
#         return generic_response

#     reset_token = oauth2.create_reset_token(user.id)
#     reset_link = f"{FRONTEND_URL}/reset-password?token={reset_token}"

#     if user.email:
#         background_tasks.add_task(
#             email_utils.send_password_reset_email,
#             to_email=user.email,
#             name=user.full_name or "there",
#             link=reset_link,
#         )
#     else:
#         _send_reset_token(user, reset_token)

#     return generic_response

@router.post("/forgot-password")
def forgot_password(
    request: schemas.ForgotPassword,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
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
        phone = request.phone_number.strip()
        user = db.query(models.User).filter(models.User.phone_number == phone).first()

        if not user:
            return generic_response

        # OTP not implemented yet — respond generically so we don't leak existence
        return generic_response

    # Shouldn't reach here — validator already enforces one of the two is present
    return generic_response




def _send_reset_token(user: models.User, token: str):
    print(f"[DEV] Password reset token for user {user.id}: {token}")


@router.post("/reset-password")
def reset_password(request: schemas.ResetPassword, db: Session = Depends(get_db)):
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