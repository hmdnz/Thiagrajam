from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app import database, models
from app.config import settings
from app.admin import models as admin_models

ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
RESET_TOKEN_EXPIRE_MINUTES = 15

# -----------------------------------------------------------------------------
# 1. OAuth2 Schemes (Distinct Swagger Auth Buttons)
# -----------------------------------------------------------------------------
# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
# admin_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/login")

# app/oauth2.py

# -----------------------------------------------------------------------------
# 1. OAuth2 Schemes (Explicit Scheme Names for Swagger UI)
# -----------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login", 
    scheme_name="UserAuth"  # <--- FORCE UNIQUE NAME
)

admin_oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/admin/login", 
    scheme_name="AdminAuth" # <--- FORCE UNIQUE NAME
)

# -----------------------------------------------------------------------------
# 2. Token Generation & Helpers
# -----------------------------------------------------------------------------
def create_access_token(data: dict):
    """Generates JWT token for both Users (user_id) and Admins (admin_id)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_reset_token(user_id: int):
    """Short-lived, single-purpose token for password reset."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    to_encode = {"user_id": user_id, "scope": "password_reset", "exp": expire}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_email_verification_token(user_id: int):
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    to_encode = {"user_id": user_id, "scope": "email_verification", "exp": expire}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_access_token(token: str, credentials_exception):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
        return user_id
    except JWTError:
        raise credentials_exception


def verify_reset_token(token: str, credentials_exception):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("scope") != "password_reset":
            raise credentials_exception
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
        return user_id
    except JWTError:
        raise credentials_exception


def verify_email_verification_token(token: str, credentials_exception):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("scope") != "email_verification":
            raise credentials_exception
        user_id = payload.get("user_id")
        if user_id is None:
            raise credentials_exception
        return user_id
    except JWTError:
        raise credentials_exception


# -----------------------------------------------------------------------------
# 3. User Dependencies (Passengers & Drivers)
# -----------------------------------------------------------------------------
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(database.get_db),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id = verify_access_token(token, credentials_exception)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user


def get_current_active_role(token: str = Depends(oauth2_scheme)) -> str:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise credentials_exception
    active_role = payload.get("active_role")
    if active_role is None:
        raise credentials_exception
    return active_role


# -----------------------------------------------------------------------------
# 4. Admin Dependencies (Admins & Super Admins)
# -----------------------------------------------------------------------------
def get_current_admin(
    token: str = Depends(admin_oauth2_scheme),
    db: Session = Depends(database.get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate admin credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        admin_id: int = payload.get("admin_id")
        if admin_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    admin = db.query(admin_models.Admin).filter(admin_models.Admin.id == admin_id).first()
    if admin is None or not admin.is_active:
        raise credentials_exception

    return admin


def get_current_super_admin(
    # Explicitly bind token to admin_oauth2_scheme so OpenAPI extracts the scheme metadata
    token: str = Depends(admin_oauth2_scheme),
    current_admin: admin_models.Admin = Depends(get_current_admin)
):
    """Only allows access to active Super Admins."""
    if not current_admin.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation reserved for Super Admins only."
        )
    return current_admin