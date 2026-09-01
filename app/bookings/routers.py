from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app import models, oauth2
from app.database import get_db
from app.bookings import models as booking_models, schemas as booking_schemas

router = APIRouter(prefix="/bookings", tags=["Bookings"])

@router.post("/", response_model=booking_schemas.BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(
    booking: booking_schemas.BookingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user)
):
    new_booking = booking_models.Booking(passenger_id=current_user.id, **booking.model_dump())
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)
    return new_booking

@router.get("/my-bookings", response_model=List[booking_schemas.BookingOut])
def get_user_bookings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user)
):
    return db.query(booking_models.Booking).filter(booking_models.Booking.passenger_id == current_user.id).all()