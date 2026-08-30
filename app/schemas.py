from typing import Optional, Literal
from pydantic import BaseModel, Field, EmailStr, model_validator, ConfigDict
from datetime import datetime, date
import re
from enum import Enum

# Import the enums from models - SINGLE SOURCE OF TRUTH.
# Schemas should never redefine these enums separately, or they'll
# eventually drift out of sync with the actual database columns.
from .models import UserRoleEnum, BloodGroupEnum, VerificationStatusEnum

# Re-export for convenience, so other files can `from .schemas import UserRole`
# instead of reaching into .models directly.
UserRole = UserRoleEnum

# ==========================================================
# POST SCHEMAS
# ==========================================================

class PostBase(BaseModel):
    # Shared fields between creating and reading a post.
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    published: bool = True
    rating: Optional[int] = Field(default=None, ge=0, le=5)

class PostCreate(PostBase):
    # Nothing extra needed for creation — inherits everything from PostBase.
    pass

class PostResponse(PostBase):
    # What gets returned to the client — adds server-generated fields.
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)  # allows building this from an ORM object directly


# ==========================================================
# AUTH / USER ACCOUNT SCHEMAS
# ==========================================================

class UserCreate(BaseModel):
    """Payload for POST /users (registration)."""
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    password: str
    role: UserRoleEnum = UserRoleEnum.passenger  # Default role

    @model_validator(mode="after")
    def validate_contact(self):
        """Ensures the user gave at least a valid email or phone number,
        and that a provided phone number is well-formed."""
        email = self.email
        phone = self.phone_number

        # Remove whitespace
        if isinstance(phone, str):
            phone = phone.strip()
            self.phone_number = phone

        # Either email or phone must be provided
        if not email and not phone:
            raise ValueError("A valid email or phone number must be provided.")

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
    """Payload for POST /login."""
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    password: str

    @model_validator(mode="after")
    def validate_contact(self):
        # Same validation logic as UserCreate — kept duplicated here
        # rather than shared, since login/registration schemas are allowed
        # to diverge later without affecting each other.
        email = self.email
        phone = self.phone_number

        if isinstance(phone, str):
            phone = phone.strip()
            self.phone_number = phone

        if not email and not phone:
            raise ValueError("A valid email or phone number must be provided.")

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
    """Payload for POST /forgot-password. Exactly one of email/phone_number
    must be given — never both, never neither."""
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
    """Payload for POST /reset-password. `token` is the reset JWT
    emailed/texted to the user."""
    token: str
    new_password: str = Field(..., min_length=8)

def validate_password_strength(password: str) -> list[str]:
    """Returns a list of human-readable error strings for any password
    strength rule that's violated. Empty list means the password passes."""
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

class VerifyOTP(BaseModel):
    """Payload for POST /verify-otp."""
    phone_number: str
    otp: str


class ResendOTP(BaseModel):
    """Payload for POST /resend-otp."""
    phone_number: str

class UserOut(BaseModel):
    """What gets returned after registration/login. Includes the JWT
    so the frontend can store it immediately without a second request."""
    id: int
    email: EmailStr | None = None
    phone_number: str | None = None
    is_active: bool
    role: UserRoleEnum
    profile_complete: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Populated manually in the create_user route — not real DB columns.
    access_token: Optional[str] = None
    token_type: Optional[str] = None

    # Computed fields for backward compatibility with older frontend code
    # that expects boolean role flags instead of a single `role` enum.
    @property
    def is_passenger(self) -> bool:
        return self.role == UserRoleEnum.passenger

    @property
    def is_driver(self) -> bool:
        return self.role == UserRoleEnum.driver

    model_config = ConfigDict(from_attributes=True)

class ChangePasswordRequest(BaseModel):
    """Payload for changing password while logged in (different from the
    forgot-password/reset-password flow, which doesn't need the old password)."""
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

class UserRoleUpdate(BaseModel):
    """Schema for updating just the user's role directly (kept for any
    existing endpoint that switches role without going through
    /profile/me/become-driver)."""
    role: UserRoleEnum

class Token(BaseModel):
    # Standard OAuth2 bearer token response shape.
    access_token: str
    token_type: str

class TokenData(BaseModel):
    # Decoded payload shape when reading claims out of a JWT.
    id: Optional[int] = None


# ==========================================================
# PASSENGER / USER PROFILE SCHEMAS
# ==========================================================
# These mirror models.User's real columns exactly. The old version of
# this schema referenced a `bio` field that was never an actual column
# on User, so it silently never persisted — removed here.

class UserProfileUpdate(BaseModel):
    """Used for every profile save — partial or full. Nothing is required,
    so the frontend can submit one field at a time in a multi-step form.
    Selfie upload is handled separately via POST /profile/me/selfie
    since it's a file, not JSON."""
    full_name: Optional[str] = None
    address: Optional[str] = None
    date_of_birth: Optional[date] = None
    next_of_kin_name: Optional[str] = None
    next_of_kin_relationship: Optional[str] = None
    emergency_contact: Optional[str] = None
    blood_group: Optional[BloodGroupEnum] = None
    health_conditions: Optional[str] = None
    nin: Optional[str] = None  # locked after first submission — enforced in the route, not here

class UserProfileOut(BaseModel):
    """What GET/PUT /profile/me return. Mirrors every relevant User column
    so the frontend has everything it needs to render the profile screen."""
    id: int
    email: Optional[str] = None
    phone_number: Optional[str] = None
    full_name: Optional[str] = None
    address: Optional[str] = None
    date_of_birth: Optional[date] = None
    next_of_kin_name: Optional[str] = None
    next_of_kin_relationship: Optional[str] = None
    emergency_contact: Optional[str] = None
    blood_group: Optional[BloodGroupEnum] = None
    health_conditions: Optional[str] = None
    nin: Optional[str] = None
    photo_url: Optional[str] = None
    nin_verification_status: VerificationStatusEnum
    nin_verified_at: Optional[datetime] = None
    nin_verification_notes: Optional[str] = None
    role: UserRoleEnum
    profile_complete: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)  # lets FastAPI build this straight from the User ORM object


# ==========================================================
# DRIVER PROFILE SCHEMAS
# ==========================================================

class DriverProfileUpdate(BaseModel):
    """Payload for PUT /profile/driver. Licence photo is handled
    separately via POST /profile/driver/license-photo since it's a
    file, not JSON."""
    license_number: Optional[str] = None  # locked after first submission — enforced in the route
    license_expiry_date: Optional[date] = None

class DriverProfileOut(BaseModel):
    """What GET/PUT /profile/driver and the licence-photo upload return."""
    id: int
    user_id: int
    license_number: Optional[str] = None
    license_photo_url: Optional[str] = None
    license_expiry_date: Optional[date] = None
    license_verification_status: VerificationStatusEnum
    license_verification_notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ==========================================================
# ADMIN SCHEMAS
# ==========================================================

class AdminRejection(BaseModel):
    """Payload for the admin reject endpoints (NIN or licence).
    `reason` is optional but strongly recommended — it's what gets
    shown back to the user via nin_verification_notes / license_verification_notes."""
    reason: Optional[str] = None