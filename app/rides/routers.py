"""
app/rides/routers.py
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date as date_type

from app import models, oauth2
from app.database import get_db
from app.cars import models as car_models
from app.rides import models as ride_models, schemas as ride_schemas
from app.bookings import models as booking_models


router = APIRouter(
    prefix="/rides",
    tags=["Rides"],
)


def _seats_remaining(
    db: Session,
    ride_id: int,
    occurrence_date: date_type,
    max_passengers: int,
) -> int:
    """
    max_passengers minus the sum of seats_booked for this
    ride on this specific date, counting only bookings that
    are still pending or confirmed (cancelled bookings free
    the seat back up).
    """

    booked = (
        db.query(
            func.coalesce(
                func.sum(booking_models.Booking.seats_booked),
                0,
            )
        )
        .filter(
            booking_models.Booking.ride_id == ride_id,
            booking_models.Booking.ride_date == occurrence_date,
            booking_models.Booking.status.in_(
                [
                    booking_models.BookingStatusEnum.pending,
                    booking_models.BookingStatusEnum.confirmed,
                ]
            ),
        )
        .scalar()
    )

    return max_passengers - int(booked)


def _create_single_ride(
    payload: ride_schemas.RideCreate,
    driver_id: int,
    db: Session,
) -> ride_models.Ride:
    """
    Creates one Ride plus its stopovers and occurrences.
    Does NOT commit — caller commits once, so a ride and its
    return ride either both save or neither does.
    """

    new_ride = ride_models.Ride(
        driver_id=driver_id,
        car_id=payload.car_id,
        pickup_location=payload.pickup_location,
        pickup_lat=payload.pickup_lat,
        pickup_lng=payload.pickup_lng,
        dropoff_location=payload.dropoff_location,
        dropoff_lat=payload.dropoff_lat,
        dropoff_lng=payload.dropoff_lng,
        pickup_time=payload.pickup_time,
        is_recurring=len(payload.dates) > 1,
        max_passengers=payload.max_passengers,
        max_back_seat_passengers=payload.max_back_seat_passengers,
        instant_booking=payload.instant_booking,
        price_per_seat=payload.price_per_seat,
    )

    db.add(new_ride)
    db.flush()  # assigns new_ride.id without committing yet

    for index, stopover in enumerate(payload.stopovers):
        db.add(
            ride_models.RideStopover(
                ride_id=new_ride.id,
                location=stopover.location,
                lat=stopover.lat,
                lng=stopover.lng,
                sequence=index,
            )
        )

    for ride_date in payload.dates:
        db.add(
            ride_models.RideOccurrence(
                ride_id=new_ride.id,
                date=ride_date,
            )
        )

    return new_ride


# ============================================================
# PUBLISH RIDE
# POST /rides/
# ============================================================

@router.post(
    "/",
    response_model=ride_schemas.RideOut,
    status_code=status.HTTP_201_CREATED,
)
def publish_ride(
    payload: ride_schemas.RideCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Publishes a ride. Requires the full eligibility chain:
    complete profile, verified NIN, verified licence — see
    User.can_offer_rides in models.py.

    If payload.return_ride is set, a second ride is created
    in the same transaction with pickup/dropoff swapped, and
    the two are linked via return_ride_id (both ways).
    """

    if not current_user.can_offer_rides:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You must have a complete profile, a "
                "verified NIN, and a verified driving "
                "licence before you can publish a ride."
            ),
        )

    car = (
        db.query(car_models.Car)
        .filter(
            car_models.Car.id == payload.car_id,
            car_models.Car.driver_id == current_user.id,
        )
        .first()
    )

    if not car:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Car not found or does not belong to you.",
        )

    outbound_ride = _create_single_ride(
        payload=payload,
        driver_id=current_user.id,
        db=db,
    )

    if payload.return_ride is not None:

        return_payload = payload.return_ride

        # Swap pickup/dropoff automatically if the caller
        # left them the same as the outbound leg — a return
        # ride is defined by going the other way.
        if (
            return_payload.pickup_location
            == payload.pickup_location
        ):
            return_payload = return_payload.model_copy(
                update={
                    "pickup_location": payload.dropoff_location,
                    "pickup_lat": payload.dropoff_lat,
                    "pickup_lng": payload.dropoff_lng,
                    "dropoff_location": payload.pickup_location,
                    "dropoff_lat": payload.pickup_lat,
                    "dropoff_lng": payload.pickup_lng,
                }
            )

        return_ride = _create_single_ride(
            payload=return_payload,
            driver_id=current_user.id,
            db=db,
        )

        outbound_ride.return_ride_id = return_ride.id
        return_ride.return_ride_id = outbound_ride.id

    db.commit()
    db.refresh(outbound_ride)

    return outbound_ride


# ============================================================
# SEARCH RIDES
# GET /rides/search
# ============================================================

@router.get(
    "/search",
    response_model=List[ride_schemas.RideSearchResult],
)
def search_rides(
    from_location: str = Query(..., alias="from"),
    to_location: str = Query(..., alias="to"),
    departure_date: date_type = Query(
        default_factory=date_type.today
    ),
    passengers: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
):
    """
    GET /rides/search?from=Birmingham&to=London&departure_date=2026-09-20&passengers=2

    departure_date defaults to today, matching "Departure:
    Today" being the default in the search form. Only rides
    with an occurrence on that exact date, with enough
    remaining seats, are returned.

    Location matching is a simple case-insensitive substring
    match for now — swap for a proper geo/places match once
    pickup_lat/pickup_lng are reliably populated from the
    frontend's Google Places integration.
    """

    candidate_rides = (
        db.query(ride_models.Ride)
        .join(ride_models.RideOccurrence)
        .filter(
            ride_models.Ride.is_active.is_(True),
            ride_models.Ride.pickup_location.ilike(
                f"%{from_location}%"
            ),
            ride_models.Ride.dropoff_location.ilike(
                f"%{to_location}%"
            ),
            ride_models.RideOccurrence.date == departure_date,
        )
        .all()
    )

    results = []

    for ride in candidate_rides:

        remaining = _seats_remaining(
            db=db,
            ride_id=ride.id,
            occurrence_date=departure_date,
            max_passengers=ride.max_passengers,
        )

        if remaining < passengers:
            continue

        result = ride_schemas.RideSearchResult(
            **ride_schemas.RideOut.model_validate(ride).model_dump(),
            searched_date=departure_date,
            seats_remaining_for_date=remaining,
        )

        results.append(result)

    return results


# ============================================================
# MY PUBLISHED RIDES
# GET /rides/my-rides
# ============================================================

@router.get(
    "/my-rides",
    response_model=List[ride_schemas.RideOut],
)
def get_my_rides(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),
):
    return (
        db.query(ride_models.Ride)
        .filter(ride_models.Ride.driver_id == current_user.id)
        .all()
    )
