"""
app/bookings/schemas.py
"""

from pydantic import BaseModel, ConfigDict
from datetime import datetime, date
from decimal import Decimal

from app.bookings.models import BookingStatusEnum


class BookingCreate(BaseModel):
    """
    CHANGED: passengers no longer supply pickup_location,
    destination, or fare — all three come from the ride
    itself. A passenger picks a ride and a date; the price
    is whatever the driver set.
    """

    ride_id: int
    ride_date: date
    seats_booked: int = 1


class BookingOut(BaseModel):
    id: int
    passenger_id: int
    ride_id: int
    ride_date: date
    seats_booked: int
    fare: Decimal
    status: BookingStatusEnum
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)