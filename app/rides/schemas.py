"""
app/rides/schemas.py
"""

import time as time_lib
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Generic, List, Optional, TypeVar
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

from app.rides.models import RecurrenceType

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    limit: int
    total_pages: int


class RideBase(BaseModel):
    origin_city: str
    pickup_location: str
    pickup_lat: Optional[float] = Field(
        None, ge=-90.0, le=90.0, description="Latitude for pickup location"
    )
    pickup_lng: Optional[float] = Field(
        None, ge=-180.0, le=180.0, description="Longitude for pickup location"
    )

    destination_city: str
    dropoff_location: str
    dropoff_lat: Optional[float] = Field(
        None, ge=-90.0, le=90.0, description="Latitude for dropoff location"
    )
    dropoff_lng: Optional[float] = Field(
        None, ge=-180.0, le=180.0, description="Longitude for dropoff location"
    )

    pickup_time: time
    price_per_seat: float = Field(gt=0, description="Price per seat in Naira")
    max_passengers: int = Field(
        gt=0, description="Maximum number of available seats"
    )

    is_recurring: bool = False
    recurrence_type: Optional[RecurrenceType] = None
    custom_days: Optional[List[int]] = None

    start_date: Optional[date] = None
    end_date: Optional[date] = None


class StopoverIn(BaseModel):
    location: Optional[str] = None
    city_name: Optional[str] = None
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    order: Optional[int] = None
    price_from_origin: Optional[float] = 0.0


class StopoverOut(BaseModel):
    id: int
    ride_id: int
    order: int = Field(
        ...,
        validation_alias=AliasChoices("order_index", "order"),
    )
    price_from_origin: Optional[float] = 0.0
    lat: Optional[float] = None
    lng: Optional[float] = None
    city_name: Optional[str] = None
    location: Optional[str] = Field(
        default=None, validation_alias="location_name"
    )
    address: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class OccurrenceOut(BaseModel):
    id: int
    date: date

    model_config = ConfigDict(from_attributes=True)


class CarSummaryOut(BaseModel):
    id: int
    make: str
    model: str
    year: int
    color: str
    is_tinted: bool
    has_wifi: bool
    has_air_conditioning: bool
    has_power_outlets: bool
    smoking_allowed: bool
    pets_allowed: bool
    wheelchair_accessible: bool

    model_config = ConfigDict(from_attributes=True)


class RideCreate(BaseModel):
    """Payload for POST /rides/."""

    car_id: int

    # Macro Journey
    origin_city: str
    destination_city: str

    # Micro Meeting Points
    pickup_location: str
    pickup_lat: Optional[float] = None
    pickup_lng: Optional[float] = None

    dropoff_location: str
    dropoff_lat: Optional[float] = None
    dropoff_lng: Optional[float] = None

    stopovers: List[StopoverIn] = Field(default_factory=list)

    # Allow single 'start_date' or list of 'dates'
    dates: List[date] = Field(
        default_factory=list, description="List of ride occurrence dates"
    )
    start_date: Optional[date] = None

    pickup_time: time

    max_passengers: int = Field(..., ge=1)
    max_back_seat_passengers: Optional[int] = Field(
        default=None, ge=0, le=3
    )

    instant_booking: bool = False
    price_per_seat: Decimal = Field(..., gt=0)

    @model_validator(mode="before")
    @classmethod
    def populate_start_date_and_dates(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # 1. If 'start_date' passed instead of 'dates', create 'dates' list
            if data.get("start_date") and not data.get("dates"):
                data["dates"] = [data["start_date"]]
            # 2. If 'dates' passed instead of 'start_date', populate 'start_date'
            elif data.get("dates") and not data.get("start_date"):
                sorted_dates = sorted(data["dates"])
                data["start_date"] = sorted_dates[0]
        return data

    @model_validator(mode="after")
    def validate_ride_constraints(self):
        if not self.dates:
            raise ValueError("At least one date or start_date must be provided.")

        if (
            self.max_back_seat_passengers is not None
            and self.max_passengers is not None
            and self.max_back_seat_passengers > self.max_passengers
        ):
            raise ValueError(
                "max_back_seat_passengers cannot be greater than max_passengers."
            )

        return self


class RideOut(RideBase):
    id: int
    driver_id: UUID
    car_id: Optional[int] = None
    is_recurring: bool = False
    is_active: bool = True

    # Coordinates
    pickup_lat: Optional[float] = None
    pickup_lng: Optional[float] = None
    dropoff_lat: Optional[float] = None
    dropoff_lng: Optional[float] = None

    created_at: datetime
    updated_at: Optional[datetime] = None

    stopovers: List[StopoverOut] = []
    occurrences: List[OccurrenceOut] = []
    car: Optional[CarSummaryOut] = None

    model_config = ConfigDict(from_attributes=True)


class RideSearchResult(RideOut):
    searched_date: date
    seats_remaining_for_date: int