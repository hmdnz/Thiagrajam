from pydantic import BaseModel
from datetime import datetime
from app.bookings.models import BookingStatusEnum

class BookingCreate(BaseModel):
    car_id: int
    pickup_location: str
    destination: str
    fare: float
    seats_booked: int = 1

class BookingOut(BookingCreate):
    id: int
    passenger_id: int
    status: BookingStatusEnum
    created_at: datetime

    class Config:
        from_attributes = True