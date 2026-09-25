import time as time_lib 
from datetime import date, datetime, time
from decimal import Decimal
from typing import Generic, List, Optional, TypeVar
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    limit: int
    total_pages: int


class RideBase(BaseModel):
    origin_city: Optional[str] = None
    destination_city: Optional[str] = None
    pickup_location: Optional[str] = None  # Allows None
    dropoff_location: Optional[str] = None  # Allows None
    pickup_time: time
    max_passengers: int
    max_back_seat_passengers: Optional[int] = None
    instant_booking: bool = False
    price_per_seat: Decimal


class StopoverIn(BaseModel):
    location: str
    lat: Optional[float] = None
    lng: Optional[float] = None


class StopoverOut(BaseModel):
    id: int
    ride_id: int
    order: int
    price_from_origin: float
    lat: Optional[float] = None
    lng: Optional[float] = None
    city_name: Optional[str] = None
    location: Optional[str] = Field(default=None, validation_alias="location_name")
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

    dates: List[date] = Field(
        ...,
        min_length=1,
        max_length=10,
    )

    pickup_time: time
    max_passengers: int = Field(..., ge=1)
    max_back_seat_passengers: Optional[int] = Field(
        default=None,
        ge=0,
        le=3,
    )

    instant_booking: bool = False
    price_per_seat: Decimal = Field(..., gt=0)

    @model_validator(mode="after")
    def validate_ride_constraints(self):
        if len(set(self.dates)) != len(self.dates):
            raise ValueError("Duplicate dates are not allowed.")

        if (
            self.max_back_seat_passengers is not None
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
    updated_at: Optional[datetime] = None  # Allows None

    stopovers: List[StopoverOut] = []
    occurrences: List[OccurrenceOut] = []
    car: Optional[CarSummaryOut] = None

    model_config = ConfigDict(from_attributes=True)


class RideSearchResult(RideOut):
    searched_date: date
    seats_remaining_for_date: int