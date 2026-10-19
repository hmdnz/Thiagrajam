from app.s3_service import generate_presigned_url
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_serializer


class CarPhotoOut(BaseModel):
    id: int
    photo_url: str
    
    created_at: datetime

    @field_serializer("photo_url")
    def serialize_photo_url(self, value: str, _info) -> str:
        if not value:
            return value

        # Already a complete external URL — leave it unchanged.
        if value.startswith(("http://", "https://")):
            return value

        # S3 object key — convert it to a temporary signed URL.
        return generate_presigned_url(value)


    model_config = {
        "from_attributes": True,
    }


class CarOut(BaseModel):
    id: int
    driver_id: UUID
    make: str
    model: str
    year: int
    color: str
    plate_number: Optional[str] = None
    capacity: int
    is_tinted: bool
    has_wifi: bool
    has_air_conditioning: bool
    has_power_outlets: bool
    smoking_allowed: bool
    pets_allowed: bool
    wheelchair_accessible: bool
    created_at: datetime
    photos: List[CarPhotoOut] = []

    model_config = {
        "from_attributes": True,
    }


class CarUpdate(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    color: Optional[str] = None
    plate_number: Optional[str] = None
    capacity: Optional[int] = None
    is_tinted: Optional[bool] = None
    has_wifi: Optional[bool] = None
    has_air_conditioning: Optional[bool] = None
    has_power_outlets: Optional[bool] = None
    smoking_allowed: Optional[bool] = None
    pets_allowed: Optional[bool] = None
    wheelchair_accessible: Optional[bool] = None



