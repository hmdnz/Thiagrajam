from typing import Optional, Literal
from pydantic import BaseModel, Field, EmailStr, model_validator, ConfigDict
from datetime import datetime, date
import re
from enum import Enum

# Import the enum from models - SINGLE SOURCE OF TRUTH
from .models import UserRoleEnum

# Re-export for convenience
UserRole = UserRoleEnum

# ==========================================================
# PYDANTIC MODELS
# ==========================================================

# Base model containing the common fields for a post.
class PostBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    published: bool = True
    rating: Optional[int] = Field(default=None, ge=0, le=5)

class PostCreate(PostBase):
    pass    

class PostResponse(PostBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class UserCreate(BaseModel):
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    password: str
    role: UserRoleEnum = UserRoleEnum.passenger  # Default role

    @model_validator(mode="after")
    def validate_contact(self):
        email = self.email
        phone = self.phone_number

        # Remove whitespace
        if isinstance(phone, str):
            phone = phone.strip()
            self.phone_number = phone

        # Either email or phone must be provided
        if not email and not phone:
            raise ValueError(
                "A valid email or phone number must be provided."
            )

        # Validate phone if provided
        if phone:
            if len(phone) > 15:
                raise ValueError(
                    "Phone number must not exceed 15 characters including the '+' sign."
                )
            if not re.fullmatch(r"\+?\d{1,14}", phone):
                raise ValueError(
                    "Phone number must contain only digits and may start with a single '+'."
                )

        return self

class UserLogin(BaseModel):
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    password: str

    @model_validator(mode="after")
    def validate_contact(self):
        email = self.email
        phone = self.phone_number

        # Remove whitespace
        if isinstance(phone, str):
            phone = phone.strip()
            self.phone_number = phone

        # Either email or phone must be provided
        if not email and not phone:
            raise ValueError(
                "A valid email or phone number must be provided."
            )

        # Validate phone if provided
        if phone:
            if len(phone) > 15:
                raise ValueError(
                    "Phone number must not exceed 15 characters including the '+' sign."
                )
            if not re.fullmatch(r"\+?\d{1,14}", phone):
                raise ValueError(
                    "Phone number must contain only digits and may start with a single '+'."
                )

        return self

class ForgotPassword(BaseModel):
    email: Optional[str] = None
    phone_number: Optional[str] = None

    @model_validator(mode="after")
    def validate_contact(self):
        if not self.email and not self.phone_number:
            raise ValueError("A valid email or phone number must be provided.")
        if self.email and self.phone_number:
            raise ValueError("Provide either an email or a phone number, not both.")
        return self

class ResetPassword(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)

def validate_password_strength(password: str) -> list[str]:
    errors = []
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        errors.append("Password must contain at least one number.")
    if not re.search(r"[^\w\s]", password):
        errors.append("Password must contain at least one special character.")
    return errors

class UserOut(BaseModel):
    id: int
    email: EmailStr | None = None
    phone_number: str | None = None
    is_active: bool
    role: UserRoleEnum
    profile_complete: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Computed fields for backward compatibility
    @property
    def is_passenger(self) -> bool:
        return self.role == UserRoleEnum.passenger
    
    @property
    def is_driver(self) -> bool:
        return self.role == UserRoleEnum.driver

    model_config = ConfigDict(from_attributes=True)

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)

    @model_validator(mode="after")
    def check_passwords(self):
        if self.new_password != self.confirm_password:
            raise ValueError("new_password and confirm_password do not match.")
        if self.new_password == self.current_password:
            raise ValueError("New password must be different from the current password.")

        errors = validate_password_strength(self.new_password)
        if errors:
            raise ValueError(" ".join(errors))

        return self

class UserProfileUpdate(BaseModel):
    """Used for every save — partial or full. Nothing is required, so
    the user can submit one field at a time if the frontend does a
    multi-step form."""
    full_name: Optional[str] = None
    address: Optional[str] = None
    phone_number: Optional[str] = None
    emergency_contact: Optional[str] = None
    photo_url: Optional[str] = None
    bio: Optional[str] = None
    nin: Optional[str] = None
    date_of_birth: Optional[date] = None
    role: Optional[UserRoleEnum] = None  # Allow role updates

class UserProfileOut(BaseModel):
    id: int
    full_name: Optional[str] = None
    address: Optional[str] = None
    phone_number: Optional[str] = None
    emergency_contact: Optional[str] = None
    photo_url: Optional[str] = None
    bio: Optional[str] = None
    nin: Optional[str] = None
    date_of_birth: Optional[date] = None
    role: UserRoleEnum
    profile_complete: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class UserRoleUpdate(BaseModel):
    """Schema for updating just the user's role"""
    role: UserRoleEnum

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    id: Optional[int] = None