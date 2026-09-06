from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from app.models import VerificationStatusEnum, UserRoleEnum # Existing imports maintained[cite: 1.2.1]

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Existing Login/View Schemas (Maintained) ---
class AdminLogin(BaseModel):
    email: EmailStr # Changed from str for basic validation[cite: 1.2.1]
    password: str

class VerificationAction(BaseModel):
    notes: Optional[str] = None

class AdminUserView(BaseModel):
    id: int
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None # Consistent validation[cite: 1.2.1]
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

# --- NEW: Schemas for Admin Management (Required for Super Admin Route) ---

class AdminCreate(BaseModel):
    """Data required by Super Admin to create a new Admin account."""
    full_name: str
    email: EmailStr
    password: str = Field(..., min_length=8) # Basic password security[cite: 1.2.1]

class AdminOut(BaseModel):
    """The public view of an Admin account."""
    id: int
    full_name: str
    email: EmailStr
    is_active: bool
    is_super_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True