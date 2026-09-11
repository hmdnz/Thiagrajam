"""
app/schemas.py

Pydantic schemas for request/response validation.

Includes:
- Post schemas
- Authentication schemas
- User schemas
- Profile schemas
- Driver profile schemas
- Admin schemas
"""

from typing import Optional, List

from pydantic import (
    BaseModel,
    Field,
    EmailStr,
    model_validator,
    ConfigDict,
)

from datetime import datetime, date

import re

from .models import (
    UserRoleEnum,
    GenderEnum,
    BloodGroupEnum,
    VerificationStatusEnum,
    ChattinessEnum,
    MusicEnum,
    SmokingEnum,
    PetsEnum,
)


# ---------------------------------------------------------------
# Enum aliases
# ---------------------------------------------------------------

UserRole = UserRoleEnum
Gender = GenderEnum
BloodGroup = BloodGroupEnum
VerificationStatus = VerificationStatusEnum

DriverChattiness = ChattinessEnum
DriverMusic = MusicEnum
DriverSmoking = SmokingEnum
DriverPets = PetsEnum


# ===============================================================
# POST SCHEMAS
# ===============================================================

class PostBase(BaseModel):
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
    )

    content: str = Field(
        ...,
        min_length=1,
    )

    published: bool = True

    rating: Optional[int] = Field(
        default=None,
        ge=0,
        le=5,
    )


class PostCreate(PostBase):
    pass


class PostResponse(PostBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


# ===============================================================
# AUTH / USER ACCOUNT SCHEMAS
# ===============================================================

class UserCreate(BaseModel):
    """
    Payload for POST /users.

    New accounts are passengers by default.

    Driver status is NOT granted through registration.
    Driver status requires a verified DriverProfile.
    """

    email: Optional[EmailStr] = None

    phone_number: Optional[str] = None

    password: str

    # Kept for compatibility with the existing API.
    # It must NOT be used to grant driver capability.
    role: UserRoleEnum = UserRoleEnum.passenger

    @model_validator(mode="after")
    def validate_contact(self):
        email = self.email
        phone = self.phone_number

        if isinstance(phone, str):
            phone = phone.strip()
            self.phone_number = phone

        if not email and not phone:
            raise ValueError(
                "A valid email or phone number must be provided."
            )

        if phone:
            if len(phone) > 15:
                raise ValueError(
                    "Phone number must not exceed 15 characters "
                    "including the '+' sign."
                )

            if not re.fullmatch(
                r"^\+?\d{1,14}$",
                phone,
            ):
                raise ValueError(
                    "Phone number must contain only digits "
                    "and may start with a single '+'."
                )

        return self


class UserLogin(BaseModel):
    """
    Payload for POST /login.
    """

    email: Optional[EmailStr] = None

    phone_number: Optional[str] = None

    password: str

    @model_validator(mode="after")
    def validate_contact(self):
        email = self.email
        phone = self.phone_number

        if isinstance(phone, str):
            phone = phone.strip()
            self.phone_number = phone

        if not email and not phone:
            raise ValueError(
                "A valid email or phone number must be provided."
            )

        if phone:
            if len(phone) > 15:
                raise ValueError(
                    "Phone number must not exceed 15 characters "
                    "including the '+' sign."
                )

            if not re.fullmatch(
                r"^\+?\d{1,14}$",
                phone,
            ):
                raise ValueError(
                    "Phone number must contain only digits "
                    "and may start with a single '+'."
                )

        return self


class ForgotPassword(BaseModel):
    """
    Payload for forgot password.

    Exactly one of email or phone_number must be supplied.
    """

    email: Optional[str] = None

    phone_number: Optional[str] = None

    @model_validator(mode="after")
    def validate_contact(self):
        if not self.email and not self.phone_number:
            raise ValueError(
                "A valid email or phone number must be provided."
            )

        if self.email and self.phone_number:
            raise ValueError(
                "Provide either an email or a phone number, not both."
            )

        return self


class ResetPassword(BaseModel):
    """
    Payload for resetting password.
    """

    token: str

    new_password: str = Field(
        ...,
        min_length=8,
    )


def validate_password_strength(
    password: str,
) -> List[str]:
    """
    Returns password strength errors.
    """

    errors = []

    if not re.search(r"[A-Z]", password):
        errors.append(
            "Password must contain at least one uppercase letter."
        )

    if not re.search(r"[a-z]", password):
        errors.append(
            "Password must contain at least one lowercase letter."
        )

    if not re.search(r"\d", password):
        errors.append(
            "Password must contain at least one number."
        )

    if not re.search(r"[^\w\s]", password):
        errors.append(
            "Password must contain at least one special character."
        )

    return errors


class VerifyOTP(BaseModel):
    """
    Payload for POST /verify-otp.
    """

    phone_number: str
    otp: str


class ResendOTP(BaseModel):
    """
    Payload for POST /resend-otp.
    """

    phone_number: str


# ===============================================================
# USER RESPONSE
# ===============================================================

class UserOut(BaseModel):
    """
    User response returned to the React frontend.

    Capability fields are computed from the user's actual
    verification/application state.
    """

    id: int

    email: Optional[EmailStr] = None

    phone_number: Optional[str] = None

    is_active: bool

    nin_verified: bool

    role: UserRoleEnum

    profile_complete: bool

    # -----------------------------------------------------------
    # Capability fields
    # -----------------------------------------------------------

    is_passenger: bool

    is_driver: bool

    has_driver_application: bool

    driver_application_status: Optional[
        VerificationStatusEnum
    ] = None

    can_book_rides: bool

    can_offer_rides: bool

    created_at: datetime

    updated_at: Optional[datetime] = None

    # -----------------------------------------------------------
    # Authentication response fields
    # -----------------------------------------------------------

    access_token: Optional[str] = None

    token_type: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True
    )


class ChangePasswordRequest(BaseModel):
    """
    Payload for changing password while logged in.
    """

    current_password: str = Field(
        ...,
        min_length=1,
    )

    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
    )

    confirm_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
    )

    @model_validator(mode="after")
    def check_passwords(self):
        if self.new_password != self.confirm_password:
            raise ValueError(
                "new_password and confirm_password do not match."
            )

        if self.new_password == self.current_password:
            raise ValueError(
                "New password must be different from "
                "the current password."
            )

        errors = validate_password_strength(
            self.new_password
        )

        if errors:
            raise ValueError(
                " ".join(errors)
            )

        return self


class UserRoleUpdate(BaseModel):
    """
    Legacy schema kept for compatibility.

    IMPORTANT:
    Changing this value does NOT determine actual driver
    capability. Driver capability comes from DriverProfile
    verification.
    """

    role: UserRoleEnum


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    id: Optional[int] = None


# ===============================================================
# DRIVER TRAVEL PREFERENCES
# ===============================================================

class DriverPreferencesResponse(BaseModel):
    """
    Driver travel preferences.
    """

    chattiness: Optional[ChattinessEnum] = None

    music: Optional[MusicEnum] = None

    smoking: Optional[SmokingEnum] = None

    pets: Optional[PetsEnum] = None

    model_config = ConfigDict(
        from_attributes=True
    )


# ===============================================================
# USER PROFILE
# ===============================================================

class UserProfileUpdate(BaseModel):
    """
    Payload for updating common user profile information.

    Profile photo is handled through the dedicated upload endpoint.
    """

    full_name: Optional[str] = None

    address: Optional[str] = None

    date_of_birth: Optional[date] = None

    gender: Optional[GenderEnum] = None

    phone_number: Optional[str] = None

    next_of_kin_name: Optional[str] = None

    next_of_kin_relationship: Optional[str] = None

    emergency_contact: Optional[str] = None

    blood_group: Optional[BloodGroupEnum] = None

    health_conditions: Optional[str] = None

    nin: Optional[str] = None

    photo_url: Optional[str] = Field(
        default=None,
        json_schema_extra={
            "example": "https://example.com/photos/avatar.png"
        },
    )

    model_config = ConfigDict(
        from_attributes=True
    )


class UserProfileOut(BaseModel):
    """
    User profile returned to React.
    """

    id: int

    email: Optional[str] = None

    phone_number: Optional[str] = None

    full_name: Optional[str] = None

    address: Optional[str] = None

    date_of_birth: Optional[date] = None

    gender: Optional[GenderEnum] = None

    next_of_kin_name: Optional[str] = None

    next_of_kin_relationship: Optional[str] = None

    emergency_contact: Optional[str] = None

    blood_group: Optional[BloodGroupEnum] = None

    health_conditions: Optional[str] = None

    nin: Optional[str] = None

    photo_url: Optional[str] = None

    nin_verification_status: VerificationStatusEnum

    role: UserRoleEnum

    profile_complete: bool

    # -----------------------------------------------------------
    # Capability fields for React
    # -----------------------------------------------------------

    is_passenger: bool

    is_driver: bool

    has_driver_application: bool

    driver_application_status: Optional[
        VerificationStatusEnum
    ] = None

    can_book_rides: bool

    can_offer_rides: bool

    created_at: datetime

    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


# ===============================================================
# DRIVER PROFILE
# ===============================================================

class DriverProfileUpdate(BaseModel):
    """
    Driver-specific information.

    Licence photo is uploaded separately.
    """

    license_number: Optional[str] = None

    license_expiry_date: Optional[date] = None

    about_me: Optional[str] = None

    chattiness: Optional[ChattinessEnum] = None

    music: Optional[MusicEnum] = None

    smoking: Optional[SmokingEnum] = None

    pets: Optional[PetsEnum] = None


class DriverProfileOut(BaseModel):
    """
    Driver profile returned to the frontend.
    """

    id: int

    user_id: int

    license_number: Optional[str] = None

    license_photo_url: Optional[str] = None

    license_expiry_date: Optional[date] = None

    about_me: Optional[str] = None

    chattiness: Optional[str] = None

    music: Optional[str] = None

    smoking: Optional[str] = None

    pets: Optional[str] = None

    gender: Optional[GenderEnum] = None

    license_verification_status: VerificationStatusEnum

    license_verification_notes: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True
    )


# ===============================================================
# ADMIN
# ===============================================================

class AdminRejection(BaseModel):
    """
    Payload for admin rejection endpoints.
    """

    reason: Optional[str] = None