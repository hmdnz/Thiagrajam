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