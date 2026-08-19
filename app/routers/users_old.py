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


@router.post("/verify-email", response_model=schemas.Token)
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

    access_token = oauth2.create_access_token(data={"user_id": user.id})

    return {"access_token": access_token, "token_type": "bearer"}


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

    return generic_response


def _send_reset_token(user: models.User, token: str):
    print(f"[DEV] Password reset token for user {user.id}: {token}")


@router.post("/reset-password", response_model=schemas.Token)
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

    access_token = oauth2.create_access_token(data={"user_id": user.id})

    return {"access_token": access_token, "token_type": "bearer"}