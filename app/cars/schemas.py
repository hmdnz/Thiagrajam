"""
app/cars/schemas.py
"""

from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class CarPhotoOut(BaseModel):
    id: int
    photo_url: str
    is_primary: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CarCreate(BaseModel):
    """
    Payload for POST /cars/. Photos are uploaded separately
    via POST /cars/{car_id}/photos, the same pattern as the
    profile/licence photo endpoints.
    """

    make: str
    model: str
    year: int
    color: str
    plate_number: str
    capacity: int = 4

    # Amenities — all optional, default to False if omitted.
    is_tinted: bool = False
    has_wifi: bool = False
    has_air_conditioning: bool = False
    has_power_outlets: bool = False
    smoking_allowed: bool = False
    pets_allowed: bool = False
    wheelchair_accessible: bool = False


class CarUpdate(BaseModel):
    """
    Payload for PUT /cars/{car_id}. Every field optional so a
    driver can update just the amenities, just the colour, etc.
    """

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


class CarOut(BaseModel):
    id: int
    driver_id: int
    make: str
    model: str
    year: int
    color: str
    plate_number: str
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

    model_config = ConfigDict(from_attributes=True)