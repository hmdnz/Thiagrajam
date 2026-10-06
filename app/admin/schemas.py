"""
app/admin/schemas.py — DEDICATED ADMIN SCHEMAS

Defines input/output Pydantic models for admin authentication and actions.
"""

from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from uuid import UUID
from datetime import datetime
from app.admin.models import AdminRoleEnum


class AdminCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: Optional[AdminRoleEnum] = AdminRoleEnum.VERIFICATION_OFFICER


class AdminLogin(BaseModel):
    email: EmailStr
    password: str


class AdminOut(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    role: AdminRoleEnum
    is_active: bool
    is_superadmin: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class VerificationActionPayload(BaseModel):
    reason: Optional[str] = None

# ============================================================
# VERIFICATION QUEUE / DECISIONS
# ============================================================

from datetime import date
from pydantic import Field
from app.models import VerificationStatusEnum


class VerificationDecision(BaseModel):
    """Admin's decision on a NIN or licence submission.

    status is one of: unverified, pending, verified, rejected.
    A reason is mandatory when rejecting so the user knows what to fix.
    """
    status: VerificationStatusEnum
    reason: Optional[str] = Field(default=None, max_length=1000)


class PendingUserOut(BaseModel):
    user_id: UUID
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    nin: Optional[str] = None
    photo_url: Optional[str] = None          # short-lived presigned URL
    nin_verification_status: VerificationStatusEnum
    nin_verification_notes: Optional[str] = None
    can_book_rides: bool
    is_suspended: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PendingDriverOut(BaseModel):
    user_id: UUID
    driver_profile_id: UUID
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    nin_verification_status: VerificationStatusEnum
    license_number: Optional[str] = None
    license_expiry_date: Optional[date] = None
    license_expired: bool
    license_front_url: Optional[str] = None  # presigned
    license_back_url: Optional[str] = None   # presigned
    license_photo_url: Optional[str] = None  # presigned
    license_verification_status: VerificationStatusEnum
    license_verification_notes: Optional[str] = None
    can_offer_rides: bool
    is_driver_suspended: bool


class PendingSummaryOut(BaseModel):
    pending_nin_count: int
    pending_license_count: int


class VerificationResultOut(BaseModel):
    user_id: UUID
    status: VerificationStatusEnum
    can_book_rides: bool
    can_offer_rides: bool
    message: str


# ============================================================
# SUSPENSIONS
# ============================================================

class SuspensionPayload(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class ReinstatePayload(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=1000)


class SuspensionResultOut(BaseModel):
    target: str                  # "passenger" | "driver" | "car"
    target_id: str
    is_suspended: bool
    message: str
    rides_affected: int = 0
    bookings_cancelled: int = 0
    refunds_queued: int = 0
    trips_in_progress: int = 0
