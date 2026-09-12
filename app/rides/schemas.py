"""
app/rides/schemas.py
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Optional, List
from datetime import date, time, datetime
from decimal import Decimal


class StopoverIn(BaseModel):
    location: str
    lat: Optional[float] = None
    lng: Optional[float] = None


class StopoverOut(StopoverIn):
    id: int
    sequence: int

    model_config = ConfigDict(from_attributes=True)


class OccurrenceOut(BaseModel):
    id: int
    date: date
    seats_remaining: int  # computed, not a DB column — see router

    model_config = ConfigDict(from_attributes=True)


class RideCreate(BaseModel):
    """
    Payload for POST /rides/.

    dates: 1 to 10 dates. A single date = a one-off ride.
    More than one = a recurring ride (is_recurring is set
    automatically based on how many dates are given).
    """

    car_id: int

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

    # None = no restriction; 0, 1, or 2 = the "max in the
    # back" checkbox the driver ticks.
    max_back_seat_passengers: Optional[int] = Field(
        default=None,
        ge=0,
        le=2,
    )

    instant_booking: bool = False

    price_per_seat: Decimal = Field(..., gt=0)

    # If provided, a linked return ride is created in the
    # same request, with locations swapped automatically.
    return_ride: Optional["RideCreate"] = None

    @model_validator(mode="after")
    def validate_dates(self):
        if len(set(self.dates)) != len(self.dates):
            raise ValueError(
                "Duplicate dates are not allowed."
            )
        return self


class RideOut(BaseModel):
    id: int
    driver_id: int
    car_id: int
    pickup_location: str
    pickup_lat: Optional[float] = None
    pickup_lng: Optional[float] = None
    dropoff_location: str
    dropoff_lat: Optional[float] = None
    dropoff_lng: Optional[float] = None
    pickup_time: time
    is_recurring: bool
    max_passengers: int
    max_back_seat_passengers: Optional[int] = None
    instant_booking: bool
    price_per_seat: Decimal
    return_ride_id: Optional[int] = None
    is_active: bool
    created_at: datetime
    stopovers: List[StopoverOut] = []
    occurrences: List[OccurrenceOut] = []

    model_config = ConfigDict(from_attributes=True)


class RideSearchResult(RideOut):
    """
    Same shape as RideOut, but seats_remaining is scoped to
    the ONE searched date, not every occurrence — that's the
    number a passenger searching "today" actually cares about.
    """

    searched_date: date
    seats_remaining_for_date: int