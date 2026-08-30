from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from . import models, schemas, utils, oauth2, email_utils
from .database import get_db

router = APIRouter(prefix="/auth", tags=["Login"])

def _get_user_by_identifier(db: Session, email: str | None, phone_number: str | None):
    filters = []
    if email:
        filters.append(models.User.email == email)
    if phone_number:
        filters.append(models.User.phone_number == phone_number)
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
    roles = [{
        "role": user.role.value,
        "profile_complete": user.profile_complete,
        "verification_status": None
    }]
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "active_role": user.role.value,
        "roles": roles
    }

# @router.post("/signup", response_model=schemas.UserOut)
# def signup(payload: schemas.UserCreate, db: Session = Depends(get_db)):
#     existing = _get_user_by_identifier(db, payload.email, payload.phone_number)
#     if existing:
#         if not existing.is_verified:
#             _send_verification(db, existing, purpose="signup")
#             return existing
#         raise HTTPException(
#             status_code=status.HTTP_409_CONFLICT,
#             detail="An account with this email or phone already exists."
#         )

#     hashed_password = utils.hash(payload.password)
#     new_user = models.User(
#         email=payload.email,
#         phone_number=payload.phone_number,
#         password=hashed_password,
#         role=payload.role,
#         is_verified=False,
#         is_active=True,
#         profile_complete=False
#     )
#     db.add(new_user)
#     db.commit()
#     db.refresh(new_user)

#     _send_verification(db, new_user, purpose="signup")
#     return new_user

# @router.post("/verify-otp")
# def verify_otp(payload: dict, db: Session = Depends(get_db)):
#     user = _get_user_by_identifier(db, payload.get("email"), payload.get("phone_number"))
#     if not user:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")
    
#     user.is_verified = True
#     db.commit()
#     db.refresh(user)
#     return _issue_token(user)

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

# @router.get("/me", response_model=schemas.UserOut)
# def get_me(current_user: models.User = Depends(oauth2.get_current_user)):
#     return current_user