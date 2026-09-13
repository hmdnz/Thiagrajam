"""
app/bookings/routers.py
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session
from typing import List, Optional

from app import models, oauth2
from app.database import get_db
from app.bookings import (
    models as booking_models,
    schemas as booking_schemas,
)
from app.rides import models as ride_models


router = APIRouter(
    prefix="/bookings",
    tags=["Bookings"],
)


# ============================================================
# ADMIN: ALL BOOKINGS
# GET /bookings/all
# ============================================================

@router.get(
    "/all",
    response_model=List[booking_schemas.BookingOut],
)
def get_all_bookings(
    status_filter: Optional[booking_models.BookingStatusEnum] = None,
    ride_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Admin-only: returns every booking in the system, optionally
    filtered by status and/or ride_id.

    GET /bookings/all
    GET /bookings/all?status_filter=pending
    GET /bookings/all?ride_id=7
    """

    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )

    query = db.query(booking_models.Booking)

    if status_filter is not None:
        query = query.filter(
            booking_models.Booking.status == status_filter
        )

    if ride_id is not None:
        query = query.filter(
            booking_models.Booking.ride_id == ride_id
        )

    return query.order_by(
        booking_models.Booking.created_at.desc()
    ).all()


# ============================================================
# CREATE BOOKING
# POST /bookings/
# ============================================================

@router.post(
    "/",
    response_model=booking_schemas.BookingOut,
    status_code=status.HTTP_201_CREATED,
)
def create_booking(
    booking: booking_schemas.BookingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Creates a passenger booking against a published ride.

    A user can only book when:
    - profile is complete
    - NIN is verified
    (current_user.can_book_rides — unchanged from before)

    Users can still search and view rides without a
    verified NIN.
    """

    # ========================================================
    # BOOKING ELIGIBILITY
    # ========================================================

    if not current_user.can_book_rides:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You cannot book a ride until your profile "
                "is complete and your NIN has been verified."
            ),
        )

    # ========================================================
    # RIDE MUST EXIST AND BE ACTIVE
    # ========================================================

    ride = (
        db.query(ride_models.Ride)
        .filter(
            ride_models.Ride.id == booking.ride_id,
            ride_models.Ride.is_active.is_(True),
        )
        .first()
    )

    if not ride:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ride not found or no longer active.",
        )

    # ========================================================
    # RIDE MUST RUN ON THE REQUESTED DATE
    # ========================================================

    occurrence_exists = (
        db.query(ride_models.RideOccurrence)
        .filter(
            ride_models.RideOccurrence.ride_id == ride.id,
            ride_models.RideOccurrence.date == booking.ride_date,
        )
        .first()
    )

    if not occurrence_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This ride does not run on the selected date.",
        )

    # ========================================================
    # SEAT AVAILABILITY
    # ========================================================

    already_booked = (
        db.query(booking_models.Booking)
        .filter(
            booking_models.Booking.ride_id == ride.id,
            booking_models.Booking.ride_date == booking.ride_date,
            booking_models.Booking.status.in_(
                [
                    booking_models.BookingStatusEnum.pending,
                    booking_models.BookingStatusEnum.confirmed,
                ]
            ),
        )
        .all()
    )

    seats_taken = sum(b.seats_booked for b in already_booked)
    seats_remaining = ride.max_passengers - seats_taken

    if booking.seats_booked > seats_remaining:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Only {seats_remaining} seat(s) left on "
                "this ride for the selected date."
            ),
        )

    # ========================================================
    # BACK-SEAT LIMIT
    # Not tracked as a separate seat type yet — this is a
    # placeholder for when the frontend distinguishes front
    # vs. back seat bookings.
    # ========================================================

    # (No enforcement here yet — flagging in case the
    # frontend needs "front/back" seat selection added to
    # BookingCreate before this can be checked properly.)

    # ========================================================
    # FARE — computed server-side, never trusted from client
    # ========================================================

    fare = ride.price_per_seat * booking.seats_booked

    # ========================================================
    # INSTANT BOOKING VS. PENDING REVIEW
    # ========================================================

    initial_status = (
        booking_models.BookingStatusEnum.confirmed
        if ride.instant_booking
        else booking_models.BookingStatusEnum.pending
    )

    new_booking = booking_models.Booking(
        passenger_id=current_user.id,
        ride_id=ride.id,
        ride_date=booking.ride_date,
        seats_booked=booking.seats_booked,
        fare=fare,
        status=initial_status,
    )

    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)

    return new_booking


# ============================================================
# MY BOOKINGS
# GET /bookings/my-bookings
# ============================================================

@router.get(
    "/my-bookings",
    response_model=List[booking_schemas.BookingOut],
)
def get_user_bookings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),
):
    return (
        db.query(booking_models.Booking)
        .filter(
            booking_models.Booking.passenger_id
            == current_user.id
        )
        .all()
    )