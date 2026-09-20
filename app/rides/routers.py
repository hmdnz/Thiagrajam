"""
app/rides/routers.py
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date as date_type, time as time_type
from decimal import Decimal
from datetime import date, datetime
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
    occurrence_date: date,
    max_passengers: int,
) -> int:
    """
    max_passengers minus the sum of seats_booked for this
    ride on this specific date, counting only bookings that
    are still pending or confirmed.
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
            booking_models.Booking.travel_date == occurrence_date,
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
    Does NOT commit — caller commits.
    """

    new_ride = ride_models.Ride(
        driver_id=driver_id,
        car_id=payload.car_id,
        origin_city=payload.origin_city,
        destination_city=payload.destination_city,
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
    db.flush()

    # Create stopovers
    for stopover in payload.stopovers or []:
        db.add(
            ride_models.Stopover(
                ride_id=new_ride.id,
                location_name=stopover.location,
                lat=stopover.lat,
                lng=stopover.lng,
            )
        )

    # Create ride occurrences
    for ride_date in payload.dates:
        db.add(
            ride_models.RideOccurrence(
                ride_id=new_ride.id,
                date=ride_date,
                seats_remaining=payload.max_passengers,
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
    Publishes a single ride. Requires the full eligibility
    chain: complete profile, verified NIN, verified licence.
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

    try:
        new_ride = _create_single_ride(
            payload=payload,
            driver_id=current_user.id,
            db=db,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(new_ride)
    return new_ride


# ============================================================
# SEARCH / FETCH RIDES  (public — no login required)
# GET /rides/search
#
# Every filter is optional. Calling this with NO params at all
# returns every upcoming active ride.
# ============================================================

@router.get(
    "/search",
    response_model=List[ride_schemas.RideSearchResult],
)
def search_rides(
    from_location: Optional[str] = Query(default=None, alias="from"),
    to_location: Optional[str] = Query(default=None, alias="to"),
    departure_date: Optional[date_type] = Query(default=None),
    passengers: int = Query(default=1, ge=1),

    # Pick-up time window, e.g. 06:00-12:00 / 12:01-18:00 / after 18:00
    pickup_time_from: Optional[time_type] = Query(default=None),
    pickup_time_to: Optional[time_type] = Query(default=None),

    # Car type / amenities
    car_make: Optional[str] = Query(default=None),
    instant_booking: Optional[bool] = Query(default=None),
    has_wifi: Optional[bool] = Query(default=None),
    has_air_conditioning: Optional[bool] = Query(default=None),
    has_power_outlets: Optional[bool] = Query(default=None),
    smoking_allowed: Optional[bool] = Query(default=None),
    pets_allowed: Optional[bool] = Query(default=None),
    wheelchair_accessible: Optional[bool] = Query(default=None),

    max_price: Optional[Decimal] = Query(default=None),

    # "price" = cheapest first, "departure" = earliest first
    sort_by: Optional[str] = Query(default=None),

    db: Session = Depends(get_db),
):
    """
    GET /rides/search
        -> every upcoming active ride, unfiltered
    """

    query = (
        db.query(ride_models.Ride, ride_models.RideOccurrence.date)
        .join(
            ride_models.RideOccurrence,
            ride_models.RideOccurrence.ride_id == ride_models.Ride.id,
        )
        .join(
            car_models.Car,
            car_models.Car.id == ride_models.Ride.car_id,
        )
        .filter(ride_models.Ride.is_active.is_(True))
    )

    if from_location:
        query = query.filter(
            ride_models.Ride.pickup_location.ilike(f"%{from_location}%")
        )

    if to_location:
        query = query.filter(
            ride_models.Ride.dropoff_location.ilike(f"%{to_location}%")
        )

    if departure_date:
        query = query.filter(
            ride_models.RideOccurrence.date == departure_date
        )
    else:
        query = query.filter(
            ride_models.RideOccurrence.date >= date_type.today()
        )

    if pickup_time_from:
        query = query.filter(
            ride_models.Ride.pickup_time >= pickup_time_from
        )

    if pickup_time_to:
        query = query.filter(
            ride_models.Ride.pickup_time <= pickup_time_to
        )

    if car_make:
        query = query.filter(
            car_models.Car.make.ilike(f"%{car_make}%")
        )

    if instant_booking is not None:
        query = query.filter(
            ride_models.Ride.instant_booking == instant_booking
        )

    if has_wifi is not None:
        query = query.filter(car_models.Car.has_wifi == has_wifi)

    if has_air_conditioning is not None:
        query = query.filter(
            car_models.Car.has_air_conditioning == has_air_conditioning
        )

    if has_power_outlets is not None:
        query = query.filter(
            car_models.Car.has_power_outlets == has_power_outlets
        )

    if smoking_allowed is not None:
        query = query.filter(
            car_models.Car.smoking_allowed == smoking_allowed
        )

    if pets_allowed is not None:
        query = query.filter(
            car_models.Car.pets_allowed == pets_allowed
        )

    if wheelchair_accessible is not None:
        query = query.filter(
            car_models.Car.wheelchair_accessible == wheelchair_accessible
        )

    if max_price is not None:
        query = query.filter(
            ride_models.Ride.price_per_seat <= max_price
        )

    if sort_by == "price":
        query = query.order_by(ride_models.Ride.price_per_seat.asc())
    elif sort_by == "departure":
        query = query.order_by(
            ride_models.RideOccurrence.date.asc(),
            ride_models.Ride.pickup_time.asc(),
        )

    candidate_rows = query.all()  # list of (Ride, occurrence_date) tuples

    results = []

    for ride, occurrence_date in candidate_rows:

        remaining = _seats_remaining(
            db=db,
            ride_id=ride.id,
            occurrence_date=occurrence_date,
            max_passengers=ride.max_passengers,
        )

        if remaining < passengers:
            continue

        result = ride_schemas.RideSearchResult(
            **ride_schemas.RideOut.model_validate(ride).model_dump(),
            searched_date=occurrence_date,
            seats_remaining_for_date=remaining,
        )

        results.append(result)

    return results


# ============================================================
# MY PUBLISHED RIDES (driver search over their own rides)
# GET /rides/my-rides
# ============================================================

@router.get(
    "/my-rides",
    response_model=List[ride_schemas.RideOut],
)
def get_my_rides(
    pickup_location: Optional[str] = None,
    dropoff_location: Optional[str] = None,
    date_from: Optional[date_type] = None,
    date_to: Optional[date_type] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Lets a driver search/filter their own published rides.
    """

    query = (
        db.query(ride_models.Ride)
        .filter(ride_models.Ride.driver_id == current_user.id)
    )

    if pickup_location:
        query = query.filter(
            ride_models.Ride.pickup_location.ilike(f"%{pickup_location}%")
        )

    if dropoff_location:
        query = query.filter(
            ride_models.Ride.dropoff_location.ilike(f"%{dropoff_location}%")
        )

    if is_active is not None:
        query = query.filter(ride_models.Ride.is_active == is_active)

    if date_from or date_to:
        query = query.join(ride_models.RideOccurrence)

        if date_from:
            query = query.filter(
                ride_models.RideOccurrence.date >= date_from
            )

        if date_to:
            query = query.filter(
                ride_models.RideOccurrence.date <= date_to
            )

        query = query.distinct()

    return query.order_by(
        ride_models.Ride.created_at.desc()
    ).all()


# ============================================================
# ADMIN: ALL RIDES
# GET /rides/all
# ============================================================

@router.get(
    "/all",
    response_model=List[ride_schemas.RideOut],
)
def get_all_rides(
    driver_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Admin-only: returns every ride in the system.
    """

    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )

    query = db.query(ride_models.Ride)

    if driver_id is not None:
        query = query.filter(ride_models.Ride.driver_id == driver_id)

    if is_active is not None:
        query = query.filter(ride_models.Ride.is_active == is_active)

    return query.order_by(
        ride_models.Ride.created_at.desc()
    ).all()


# ============================================================
# GET SINGLE RIDE  (public — no login required)
# GET /rides/{ride_id}
#
# MUST stay below every fixed-path route above (/search,
# /my-rides, /all).
# ============================================================

@router.get(
    "/{ride_id}",
    response_model=ride_schemas.RideOut,
)
def get_ride_by_id(
    ride_id: int,
    db: Session = Depends(get_db),
):
    """
    Fetches full details for one ride.
    """

    ride = (
        db.query(ride_models.Ride)
        .filter(
            ride_models.Ride.id == ride_id,
            ride_models.Ride.is_active.is_(True),
        )
        .first()
    )

    if not ride:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ride not found.",
        )

    return ride

    
