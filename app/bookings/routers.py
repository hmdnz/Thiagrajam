"""
app/bookings/routers.py — FULL RECONCILED BOOKING ROUTER
"""

from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app import oauth2, models as user_models
from app.rides import models as ride_models
from app.bookings import models as booking_models, schemas as booking_schemas

router = APIRouter(prefix="/bookings", tags=["Bookings Module"])


# ============================================================
# 1. CREATE BOOKING (PASSENGER)
# POST /bookings/
# ============================================================
@router.post("/", response_model=booking_schemas.BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(
    booking_in: booking_schemas.BookingCreate,
    db: Session = Depends(get_db),
    current_user: user_models.User = Depends(oauth2.get_current_user)
):
    """
    Passenger requests a booking for a specific ride and date.
    Calculates total fare server-side and enforces seat limits.
    """
    if current_user.is_suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is suspended. You cannot book rides."
        )

    if not current_user.can_book_rides:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your photograph and NIN must be verified by an admin before you can book rides."
        )

    ride = db.query(ride_models.Ride).filter(ride_models.Ride.id == booking_in.ride_id).first()
    if not ride:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requested ride not found."
        )

    # A ride whose driver or car has been suspended cannot be booked.
    if ride.driver.is_driver_suspended or (ride.car and ride.car.is_suspended):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This ride is currently unavailable."
        )

    # Check available seats for the specified travel date
    active_bookings = db.query(booking_models.Booking).filter(
        booking_models.Booking.ride_id == booking_in.ride_id,
        booking_models.Booking.travel_date == booking_in.travel_date,
        booking_models.Booking.status.in_([
            booking_models.BookingStatusEnum.PENDING,
            booking_models.BookingStatusEnum.CONFIRMED,
            booking_models.BookingStatusEnum.TRIP_STARTED
        ])
    ).all()

    seats_taken = sum(b.seats_booked for b in active_bookings)
    available_seats = ride.max_passengers - seats_taken

    if booking_in.seats_booked > available_seats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only {available_seats} seat(s) available for {booking_in.travel_date}."
        )

    # Server-side fare computation
    total_fare = ride.price_per_seat * booking_in.seats_booked

    new_booking = booking_models.Booking(
        passenger_id=current_user.id,
        ride_id=ride.id,
        car_id=ride.car_id,
        travel_date=booking_in.travel_date,
        seats_booked=booking_in.seats_booked,
        fare=total_fare,
        status=booking_models.BookingStatusEnum.PENDING
    )

    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)

    return new_booking


# ============================================================
# 2. GET PASSENGER BOOKINGS
# GET /bookings/my-bookings
# ============================================================
@router.get("/my-bookings", response_model=List[booking_schemas.BookingOut])
def get_my_bookings(
    db: Session = Depends(get_db),
    current_user: user_models.User = Depends(oauth2.get_current_user)
):
    """Retrieves all bookings made by the currently logged-in passenger."""
    return db.query(booking_models.Booking).filter(
        booking_models.Booking.passenger_id == current_user.id
    ).order_by(booking_models.Booking.created_at.desc()).all()


# ============================================================
# 3. DRIVER CONFIRM BOOKING
# POST /bookings/{id}/confirm
# ============================================================
@router.post("/{booking_id}/confirm", response_model=booking_schemas.BookingOut)
def confirm_booking(
    booking_id: int,
    payload: booking_schemas.BookingDriverConfirm = booking_schemas.BookingDriverConfirm(),
    db: Session = Depends(get_db),
    current_user: user_models.User = Depends(oauth2.get_current_user)
):
    """Driver accepts/confirms a pending booking request."""
    booking = db.query(booking_models.Booking).filter(booking_models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")

    # Verify current user is the driver for this ride
    if booking.ride.driver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned driver can confirm this booking."
        )

    if booking.status != booking_models.BookingStatusEnum.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot confirm booking with current status: {booking.status.value}."
        )

    booking.status = booking_models.BookingStatusEnum.CONFIRMED
    booking.driver_confirmed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(booking)

    return booking


# ============================================================
# 4. START TRIP (DRIVER)
# POST /bookings/{id}/start-trip
# ============================================================
@router.post("/{booking_id}/start-trip", response_model=booking_schemas.BookingOut)
def start_trip(
    booking_id: int,
    payload: booking_schemas.BookingTripAction = booking_schemas.BookingTripAction(),
    db: Session = Depends(get_db),
    current_user: user_models.User = Depends(oauth2.get_current_user)
):
    """Driver marks the trip as started."""
    booking = db.query(booking_models.Booking).filter(booking_models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")

    if booking.ride.driver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned driver can start this trip."
        )

    if booking.status != booking_models.BookingStatusEnum.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Booking must be CONFIRMED before starting trip."
        )

    booking.status = booking_models.BookingStatusEnum.TRIP_STARTED
    booking.trip_started_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(booking)

    return booking


# ============================================================
# 5. COMPLETE TRIP (DRIVER)
# POST /bookings/{id}/complete-trip
# ============================================================
@router.post("/{booking_id}/complete-trip", response_model=booking_schemas.BookingOut)
def complete_trip(
    booking_id: int,
    payload: booking_schemas.BookingTripAction = booking_schemas.BookingTripAction(),
    db: Session = Depends(get_db),
    current_user: user_models.User = Depends(oauth2.get_current_user)
):
    """Driver marks the trip as completed."""
    booking = db.query(booking_models.Booking).filter(booking_models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")

    if booking.ride.driver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned driver can complete this trip."
        )

    if booking.status != booking_models.BookingStatusEnum.TRIP_STARTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trip must be in TRIP_STARTED status before completion."
        )

    booking.status = booking_models.BookingStatusEnum.TRIP_COMPLETED
    booking.trip_completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(booking)

    return booking


# ============================================================
# 6. CANCEL BOOKING (PASSENGER)
# POST /bookings/{id}/cancel
# ============================================================
@router.post("/{booking_id}/cancel", response_model=booking_schemas.BookingOut)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: user_models.User = Depends(oauth2.get_current_user)
):
    """Passenger cancels a pending or confirmed booking."""
    booking = db.query(booking_models.Booking).filter(booking_models.Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")

    if booking.passenger_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only cancel your own bookings."
        )

    if booking.status in [booking_models.BookingStatusEnum.TRIP_STARTED, booking_models.BookingStatusEnum.TRIP_COMPLETED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel a trip that has already started or completed."
        )

    booking.status = booking_models.BookingStatusEnum.CANCELLED

    db.commit()
    db.refresh(booking)

    return booking