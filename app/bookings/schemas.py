"""
app/bookings/schemas.py
"""

from pydantic import BaseModel, ConfigDict
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from app.bookings.models import BookingStatusEnum


class BookingCreate(BaseModel):
    ride_id: int
    travel_date: date
    seats_booked: int = 1


class BookingOut(BaseModel):
    id: int
    passenger_id: UUID
    ride_id: int
    car_id: Optional[int] = None
    travel_date: date
    seats_booked: int
    fare: Decimal
    status: BookingStatusEnum

    driver_confirmed_at: Optional[datetime] = None
    trip_started_at: Optional[datetime] = None
    trip_completed_at: Optional[datetime] = None
    funds_released_at: Optional[datetime] = None

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookingDriverConfirm(BaseModel):
    note: Optional[str] = None


class BookingTripAction(BaseModel):
    note: Optional[str] = None