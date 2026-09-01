from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models import VerificationStatusEnum, UserRoleEnum

class AdminLogin(BaseModel):
    email: str
    password: str

class VerificationAction(BaseModel):
    notes: Optional[str] = None

class AdminUserView(BaseModel):
    id: int
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    nin: Optional[str] = None
    photo_url: Optional[str] = None
    nin_verification_status: VerificationStatusEnum
    role: UserRoleEnum
    created_at: datetime

    class Config:
        from_attributes = True

class AdminDriverView(BaseModel):
    id: int
    user_id: int
    license_number: Optional[str] = None
    license_photo_url: Optional[str] = None
    license_verification_status: VerificationStatusEnum
    license_verification_notes: Optional[str] = None

    class Config:
        from_attributes = True

