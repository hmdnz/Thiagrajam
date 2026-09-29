"""
app/schemas.py

Pydantic schemas for request validation, authorization payloads, 
and JSON API responses.
"""

from datetime import date, datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models import (
    BloodGroupEnum,
    BookingStatusEnum,
    ChattinessEnum,
    GenderEnum,
    MusicEnum,
    PaymentStatusEnum,
    PetsEnum,
    RideStatusEnum,
    SmokingEnum,
    UserRoleEnum,
    VerificationStatusEnum,
)

# ============================================================
# USER CREATE
# ============================================================

class UserCreateOut(BaseModel):
  id: UUID | str
  email: EmailStr | None = None
  phone_number: str | None = None
  role: str
  access_token: str
  token_type: str = "bearer"

  model_config = ConfigDict(from_attributes=True)  # pydantic v2 (or orm_mode = True for v1)



# ============================================================
# AUTHENTICATION & TOKENS
# ============================================================

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    id: Optional[str] = None


class UserLogin(BaseModel):
    username_or_email_or_phone: str
    password: str


class VerifyOTP(BaseModel):
    phone_number: str
    otp: str


class ResendOTP(BaseModel):
    phone_number: str


class ForgotPassword(BaseModel):
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None


class ResetPassword(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)


# ============================================================
# DRIVER PROFILE SCHEMAS
# ============================================================

class DriverProfileBase(BaseModel):
    car_make: Optional[str] = None
    car_model: Optional[str] = None
    car_year: Optional[int] = None
    car_color: Optional[str] = None
    plate_number: Optional[str] = None
    about_me: Optional[str] = None
    chattiness: Optional[ChattinessEnum] = None
    music: Optional[MusicEnum] = None
    smoking: Optional[SmokingEnum] = None
    pets: Optional[PetsEnum] = None
    license_number: Optional[str] = None
    license_expiry_date: Optional[date] = None


class DriverProfileCreate(DriverProfileBase):
    pass


class DriverProfileUpdate(DriverProfileBase):
    license_front_url: Optional[str] = None
    license_back_url: Optional[str] = None
    license_photo_url: Optional[str] = None


class DriverPreferencesResponse(DriverProfileBase):
    id: UUID
    user_id: UUID
    license_verification_status: VerificationStatusEnum
    license_verification_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# USER & PROFILE SCHEMAS
# ============================================================

class UserBase(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    gender: Optional[GenderEnum] = None
    date_of_birth: Optional[date] = None
    address: Optional[str] = None
    blood_group: Optional[BloodGroupEnum] = None
    health_conditions: Optional[str] = None
    emergency_contact: Optional[str] = None
    next_of_kin_name: Optional[str] = None
    next_of_kin_relationship: Optional[str] = None
    nin: Optional[str] = None


class UserCreate(BaseModel):
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    password: str
    role: str = "passenger"

    @model_validator(mode="after")
    def check_at_least_one_identifier(self) -> "UserCreate":
        if not self.email and not self.phone_number:
            raise ValueError(
                "At least one contact method (email or phone_number) must be provided."
            )
        return self

class UserProfileUpdate(BaseModel):
    """
    Payload for updating user profile fields and ride preferences.
    Supports partial updates.
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
    about_me: Optional[str] = None
    photo_url: Optional[str] = None

    # Ride preferences matching payload JSON keys
    chattiness: Optional[ChattinessEnum] = None
    music: Optional[MusicEnum] = None
    smoking: Optional[SmokingEnum] = None
    pets: Optional[PetsEnum] = None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "full_name": "Mr Json Doe",
                "address": "76 string St",
                "date_of_birth": "2026-09-26",
                "gender": "male",
                "phone_number": "09012121314",
                "next_of_kin_name": "Mrs String",
                "next_of_kin_relationship": "spouse",
                "emergency_contact": "2345678987654",
                "blood_group": "A+",
                "health_conditions": "Healthy strings",
                "nin": "2345678987654",
                "about_me": "This string is about my strings",
                "chattiness": "Very talkative!",
                "music": "Always playing tunes!",
                "smoking": "Smoking allowed in the vehicle",
                "pets": "Pet-friendly ride!",
            }
        },
    )


class ProfileUpdate(UserProfileUpdate):
    """
    Alias schema for app/routers/profile.py route handlers.
    """
    pass


class UserRoleUpdate(BaseModel):
    """
    Payload for updating a user's role (e.g. by admin).
    """
    role: UserRoleEnum

    model_config = ConfigDict(from_attributes=True)


class UserOut(UserBase):
    id: UUID
    role: UserRoleEnum
    is_active: bool
    is_verified: bool
    is_admin: bool
    is_suspended: bool
    is_driver: bool
    can_offer_rides: bool
    nin_verified: bool
    nin_verification_status: VerificationStatusEnum
    photo_url: Optional[str] = None
    profile_complete: bool
    access_token: Optional[str] = None
    token_type: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileOut(UserOut):
    about_me: Optional[str] = None
    chattiness: Optional[ChattinessEnum] = None
    music_preference: Optional[MusicEnum] = None
    smoking_preference: Optional[SmokingEnum] = None
    pets_preference: Optional[PetsEnum] = None
    driver_profile: Optional[DriverPreferencesResponse] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# POST SCHEMAS
# ============================================================

class PostBase(BaseModel):
    title: str
    content: str
    published: bool = True
    rating: Optional[int] = None


class PostCreate(PostBase):
    pass


class PostOut(PostBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PostResponse(BaseModel):
    data: PostOut
    message: str


# ============================================================
# RIDE & BOOKING SCHEMAS
# ============================================================

class RideBase(BaseModel):
    origin: str
    destination: str
    departure_time: datetime
    available_seats: int
    price_per_seat: float
    origin_latitude: Optional[float] = None
    origin_longitude: Optional[float] = None
    destination_latitude: Optional[float] = None
    destination_longitude: Optional[float] = None
    notes: Optional[str] = None


class RideCreate(RideBase):
    pass


class RideOut(RideBase):
    id: UUID
    driver_id: UUID
    status: RideStatusEnum
    created_at: datetime
    updated_at: datetime
    driver: UserOut

    model_config = ConfigDict(from_attributes=True)


class BookingBase(BaseModel):
    ride_id: UUID
    seats_booked: int = 1


class BookingCreate(BookingBase):
    pass


class BookingOut(BaseModel):
    id: UUID
    ride_id: UUID
    passenger_id: UUID
    seats_booked: int
    total_price: float
    status: BookingStatusEnum
    created_at: datetime
    updated_at: datetime
    ride: RideOut

    model_config = ConfigDict(from_attributes=True)
    