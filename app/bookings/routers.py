"""
app/bookings/routers.py

Wenyfour booking API.

Responsibilities:
- Passenger booking creation
- Passenger booking history
- Driver passenger/booking visibility
- Driver booking approval
- Driver booking rejection
- Trip start
- Trip completion
- Passenger cancellation
- Driver cancellation
- Cancellation financial calculations
- Voucher creation
- Driver wallet cancellation penalty

IMPORTANT:
Financial provider refunds are NOT performed directly here.

This router records the cancellation entitlement and, where applicable,
creates the internal voucher / wallet ledger movement.

The existing payments/refunds module should process the actual provider
refund using the recorded passenger_refund_kobo entitlement.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List
from zoneinfo import ZoneInfo

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import (
    Session,
    joinedload,
)

from app.database import get_db
from app import oauth2
from app import models as user_models
from app.rides import models as ride_models
from app.bookings import (
    models as booking_models,
    schemas as booking_schemas,
)


router = APIRouter(
    prefix="/bookings",
    tags=["Bookings Module"],
)


# ============================================================
# CONSTANTS
# ============================================================

LAGOS_TZ = ZoneInfo("Africa/Lagos")

CANCELLATION_PENALTY_PERCENT = 10

VOUCHER_PERCENT_OF_PENALTY = 50

CANCELLATION_WINDOW_HOURS = 48


# ============================================================
# INTERNAL HELPERS
# ============================================================


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def _lagos_now() -> datetime:
    """Return the current timezone-aware Africa/Lagos datetime."""
    return datetime.now(LAGOS_TZ)


def _fare_to_kobo(fare: Decimal) -> int:
    """
    Convert booking fare from NGN Decimal to integer kobo.

    Example:
        26000.00 NGN -> 2600000 kobo
    """
    amount = Decimal(str(fare))

    if amount < Decimal("0"):
        raise ValueError("Booking fare cannot be negative.")

    kobo = amount * Decimal("100")

    if kobo != kobo.to_integral_value():
        raise ValueError(
            "Booking fare contains more than two decimal places."
        )

    return int(kobo)


def get_ride_departure_datetime(
    booking: booking_models.Booking,
) -> datetime:
    """
    Build the scheduled departure datetime in Africa/Lagos timezone.

    The ride model currently provides:
        booking.travel_date
        booking.ride.pickup_time
    """

    if not booking.ride:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ride information is unavailable for this booking.",
        )

    pickup_time = booking.ride.pickup_time

    if pickup_time is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ride pickup time is not configured.",
        )

    # pickup_time should normally be datetime.time.
    # If the model ever supplies an aware datetime, normalize it.
    if isinstance(pickup_time, datetime):
        if pickup_time.tzinfo is None:
            return pickup_time.replace(tzinfo=LAGOS_TZ)

        return pickup_time.astimezone(LAGOS_TZ)

    naive_departure = datetime.combine(
        booking.travel_date,
        pickup_time,
    )

    return naive_departure.replace(
        tzinfo=LAGOS_TZ,
    )


def ensure_cancellation_window_is_open(
    booking: booking_models.Booking,
) -> None:
    """
    Enforce the Wenyfour 48-hour cancellation rule.

    Neither passenger nor driver may cancel when the ride is within
    48 hours of scheduled departure.
    """

    departure = get_ride_departure_datetime(booking)

    now = _lagos_now()

    remaining = departure - now

    if remaining <= timedelta(
        hours=CANCELLATION_WINDOW_HOURS
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This ride cannot be cancelled within "
                "48 hours of the scheduled departure time."
            ),
        )


def _booking_can_be_cancelled(
    booking: booking_models.Booking,
) -> bool:
    """
    Return whether the booking is still in a cancellable state.
    """

    return booking.status in {
        booking_models.BookingStatusEnum.PENDING,
        booking_models.BookingStatusEnum.CONFIRMED,
    }


def _ensure_no_existing_cancellation(
    db: Session,
    booking_id: int,
) -> None:
    """
    Prevent duplicate cancellation records.

    The database unique constraint on booking_id is the final protection.
    This application-level check gives the user a useful API response.
    """

    existing = (
        db.query(booking_models.BookingCancellation)
        .filter(
            booking_models.BookingCancellation.booking_id
            == booking_id
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This booking already has a cancellation record.",
        )


def _driver_booking_response(
    booking: booking_models.Booking,
) -> dict:
    """
    Convert a Booking into DriverPassengerBookingOut-compatible data.
    """

    ride = booking.ride
    passenger = booking.passenger

    return {
        "booking_id": booking.id,
        "passenger_id": booking.passenger_id,
        "passenger_name": (
            passenger.full_name
            if passenger
            else None
        ),
        "passenger_email": (
            passenger.email
            if passenger
            else None
        ),
        "passenger_phone": (
            passenger.phone_number
            if passenger
            else None
        ),
        "ride_id": booking.ride_id,
        "travel_date": booking.travel_date,
        "pickup_time": ride.pickup_time,
        "pickup_location": ride.pickup_location,
        "dropoff_location": ride.dropoff_location,
        "seats_booked": booking.seats_booked,
        "fare": booking.fare,
        "status": booking.status,
        "created_at": booking.created_at,
        "driver_confirmed_at": booking.driver_confirmed_at,
    }


def _send_booking_confirmation_notifications(
    *,
    booking: booking_models.Booking,
    driver,
) -> None:
    """
    Best-effort email/SMS notification after driver approval.

    Notification failure must not undo a successful booking approval.

    The actual provider utilities are imported lazily so that a missing
    optional notification integration does not prevent the booking module
    from loading.
    """

    passenger = booking.passenger
    ride = booking.ride

    if not passenger or not ride:
        return

    notification_data = {
        "passenger_name": (
            passenger.full_name or "Passenger"
        ),
        "driver_name": (
            driver.full_name or "Your driver"
        ),
        "travel_date": booking.travel_date,
        "pickup_location": ride.pickup_location,
        "dropoff_location": ride.dropoff_location,
        "pickup_time": ride.pickup_time,
        "booking_id": booking.id,
    }

    # --------------------------------------------------------
    # EMAIL
    # --------------------------------------------------------

    if passenger.email:
        try:
            from app.email_utils import send_email

            send_email(
                to_email=passenger.email,
                subject="Your Wenyfour ride has been confirmed",
                template_name="booking_confirmed.html",
                **notification_data,
            )
        except Exception as exc:
            print(
                "[BOOKING EMAIL ERROR] "
                f"booking={booking.id}: {exc}"
            )

    # --------------------------------------------------------
    # SMS
    # --------------------------------------------------------

    if passenger.phone_number:
        try:
            from sms_utility import (
                send_booking_confirmation_sms,
            )

            send_booking_confirmation_sms(
                phone_number=passenger.phone_number,
                passenger_name=(
                    passenger.full_name
                    or "Passenger"
                ),
                driver_name=(
                    driver.full_name
                    or "Your driver"
                ),
                travel_date=str(
                    booking.travel_date
                ),
                pickup_location=(
                    ride.pickup_location
                ),
                booking_id=booking.id,
            )
        except Exception as exc:
            print(
                "[BOOKING SMS ERROR] "
                f"booking={booking.id}: {exc}"
            )


def _send_driver_rejection_notification(
    *,
    booking: booking_models.Booking,
    driver,
) -> None:
    """
    Best-effort passenger notification after driver rejection.

    The booking transaction is already committed before notifications
    are attempted.
    """

    passenger = booking.passenger
    ride = booking.ride

    if not passenger or not ride:
        return

    if passenger.email:
        try:
            from app.email_utils import send_email

            send_email(
                to_email=passenger.email,
                subject="Your Wenyfour booking was not accepted",
                template_name="booking_rejected.html",
                passenger_name=(
                    passenger.full_name
                    or "Passenger"
                ),
                driver_name=(
                    driver.full_name
                    or "The driver"
                ),
                travel_date=booking.travel_date,
                pickup_location=ride.pickup_location,
                dropoff_location=ride.dropoff_location,
                booking_id=booking.id,
            )
        except Exception as exc:
            print(
                "[BOOKING REJECTION EMAIL ERROR] "
                f"booking={booking.id}: {exc}"
            )

    # SMS provider integration can be added to the existing SMS utility
    # without changing the booking transaction.


# ============================================================
# 1. CREATE BOOKING — PASSENGER
# POST /bookings/
# ============================================================


@router.post(
    "/",
    response_model=booking_schemas.BookingOut,
    status_code=status.HTTP_201_CREATED,
)
def create_booking(
    booking_in: booking_schemas.BookingCreate,
    db: Session = Depends(get_db),
    current_user: user_models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Passenger requests a booking.

    Important:
    The ride row is locked before checking seat availability.

    This prevents two concurrent passengers from both seeing the same
    final available seat and overselling the ride.
    """

    if current_user.is_suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Your account is suspended. "
                "You cannot book rides."
            ),
        )

    if not current_user.can_book_rides:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Your photograph and NIN must be verified "
                "by an admin before you can book rides."
            ),
        )

    if booking_in.travel_date < _lagos_now().date():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot book a ride for a date in the past.",
        )

    # --------------------------------------------------------
    # LOCK RIDE ROW
    # --------------------------------------------------------

    ride = (
        db.query(ride_models.Ride)
        .filter(
            ride_models.Ride.id
            == booking_in.ride_id
        )
        .with_for_update()
        .first()
    )

    if not ride:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requested ride not found.",
        )

    # --------------------------------------------------------
    # RIDE AVAILABILITY
    # --------------------------------------------------------

    # Existing application appears to use an active flag.
    if hasattr(ride, "is_active") and not ride.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This ride is no longer active.",
        )

    if ride.driver and ride.driver.is_driver_suspended:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This ride is currently unavailable.",
        )

    if ride.car and ride.car.is_suspended:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This ride is currently unavailable.",
        )

    # --------------------------------------------------------
    # SEAT VALIDATION
    # --------------------------------------------------------

    if booking_in.seats_booked > ride.max_passengers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"This ride has a maximum capacity of "
                f"{ride.max_passengers} passenger(s)."
            ),
        )

    active_bookings = (
        db.query(booking_models.Booking)
        .filter(
            booking_models.Booking.ride_id
            == booking_in.ride_id,
            booking_models.Booking.travel_date
            == booking_in.travel_date,
            booking_models.Booking.status.in_(
                [
                    booking_models.BookingStatusEnum.PENDING,
                    booking_models.BookingStatusEnum.CONFIRMED,
                    booking_models.BookingStatusEnum.TRIP_STARTED,
                ]
            ),
        )
        .all()
    )

    seats_taken = sum(
        booking.seats_booked
        for booking in active_bookings
    )

    available_seats = (
        ride.max_passengers - seats_taken
    )

    if booking_in.seats_booked > available_seats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Only {available_seats} seat(s) "
                f"available for {booking_in.travel_date}."
            ),
        )

    # --------------------------------------------------------
    # FARE
    # --------------------------------------------------------

    total_fare = (
        ride.price_per_seat
        * booking_in.seats_booked
    )

    if Decimal(str(total_fare)) <= Decimal("0"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ride fare must be greater than zero.",
        )

    # --------------------------------------------------------
    # CREATE BOOKING
    # --------------------------------------------------------

    new_booking = booking_models.Booking(
        passenger_id=current_user.id,
        ride_id=ride.id,
        car_id=ride.car_id,
        travel_date=booking_in.travel_date,
        seats_booked=booking_in.seats_booked,
        fare=total_fare,
        status=booking_models.BookingStatusEnum.PENDING,
    )

    db.add(new_booking)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(new_booking)

    return new_booking


# ============================================================
# 2. GET PASSENGER BOOKINGS
# GET /bookings/my-bookings
# ============================================================


@router.get(
    "/my-bookings",
    response_model=List[booking_schemas.BookingOut],
)
def get_my_bookings(
    db: Session = Depends(get_db),
    current_user: user_models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Retrieve bookings belonging to the authenticated passenger.
    """

    return (
        db.query(booking_models.Booking)
        .filter(
            booking_models.Booking.passenger_id
            == current_user.id
        )
        .order_by(
            booking_models.Booking.created_at.desc()
        )
        .all()
    )


# ============================================================
# 3. DRIVER: SEE PASSENGERS
# GET /bookings/driver/bookings
# ============================================================


@router.get(
    "/driver/bookings",
    response_model=List[
        booking_schemas.DriverPassengerBookingOut
    ],
)
def get_driver_bookings(
    db: Session = Depends(get_db),
    current_user: user_models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Driver sees passengers who booked the driver's rides.
    """

    if not current_user.is_driver:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can access this endpoint.",
        )

    bookings = (
        db.query(booking_models.Booking)
        .join(
            ride_models.Ride,
            booking_models.Booking.ride_id
            == ride_models.Ride.id,
        )
        .options(
            joinedload(
                booking_models.Booking.passenger
            ),
            joinedload(
                booking_models.Booking.ride
            ),
        )
        .filter(
            ride_models.Ride.driver_id
            == current_user.id,
        )
        .order_by(
            booking_models.Booking.travel_date.asc(),
            booking_models.Booking.created_at.asc(),
        )
        .all()
    )

    return [
        _driver_booking_response(booking)
        for booking in bookings
    ]


# ============================================================
# 4. DRIVER: PENDING BOOKINGS
# GET /bookings/driver/pending
# ============================================================


@router.get(
    "/driver/pending",
    response_model=List[
        booking_schemas.DriverPassengerBookingOut
    ],
)
def get_driver_pending_bookings(
    db: Session = Depends(get_db),
    current_user: user_models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Return booking requests awaiting driver action.
    """

    if not current_user.is_driver:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only drivers can access this endpoint.",
        )

    bookings = (
        db.query(booking_models.Booking)
        .join(
            ride_models.Ride,
            booking_models.Booking.ride_id
            == ride_models.Ride.id,
        )
        .options(
            joinedload(
                booking_models.Booking.passenger
            ),
            joinedload(
                booking_models.Booking.ride
            ),
        )
        .filter(
            ride_models.Ride.driver_id
            == current_user.id,
            booking_models.Booking.status
            == booking_models.BookingStatusEnum.PENDING,
        )
        .order_by(
            booking_models.Booking.travel_date.asc(),
            booking_models.Booking.created_at.asc(),
        )
        .all()
    )

    return [
        _driver_booking_response(booking)
        for booking in bookings
    ]


# ============================================================
# 5. DRIVER CONFIRM BOOKING
# POST /bookings/{booking_id}/confirm
# ============================================================


@router.post(
    "/{booking_id}/confirm",
    response_model=booking_schemas.BookingOut,
)
def confirm_booking(
    booking_id: int,
    payload: booking_schemas.BookingDriverConfirm = None,
    db: Session = Depends(get_db),
    current_user: user_models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Driver approves a passenger.

    The booking row is locked to prevent two simultaneous approval
    requests from both succeeding.

    After approval:
        PENDING -> CONFIRMED

    Passenger receives best-effort email/SMS notification.
    """

    booking = (
        db.query(booking_models.Booking)
        .filter(
            booking_models.Booking.id == booking_id
        )
        .with_for_update()
        .first()
    )

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found.",
        )

    # Access ride after booking row is locked.
    ride = booking.ride

    if not ride:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ride information is unavailable.",
        )

    if ride.driver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Only the assigned driver can "
                "confirm this booking."
            ),
        )

    if booking.status != booking_models.BookingStatusEnum.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Only a PENDING booking can be confirmed. "
                f"Current status: {booking.status.value}."
            ),
        )

    booking.status = (
        booking_models.BookingStatusEnum.CONFIRMED
    )

    booking.driver_confirmed_at = _utc_now()

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(booking)

    # Load notification relationships after commit.
    booking = (
        db.query(booking_models.Booking)
        .options(
            joinedload(
                booking_models.Booking.passenger
            ),
            joinedload(
                booking_models.Booking.ride
            ),
        )
        .filter(
            booking_models.Booking.id == booking_id
        )
        .first()
    )

    if booking:
        _send_booking_confirmation_notifications(
            booking=booking,
            driver=current_user,
        )

    return booking


# ============================================================
# 6. DRIVER REJECT BOOKING
# POST /bookings/{booking_id}/reject
# ============================================================


@router.post(
    "/{booking_id}/reject",
    response_model=booking_schemas.BookingOut,
)
def reject_booking(
    booking_id: int,
    payload: booking_schemas.BookingDriverReject,
    db: Session = Depends(get_db),
    current_user: user_models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Driver rejects a pending passenger request.

    This is NOT the same as driver cancellation.

    A rejection occurs before driver acceptance and therefore:
    - no driver cancellation penalty
    - no passenger cancellation penalty
    - if payment exists, refund entitlement is the full booking amount

    Actual provider refund processing belongs to the payment/refund module.
    """

    booking = (
        db.query(booking_models.Booking)
        .filter(
            booking_models.Booking.id == booking_id
        )
        .with_for_update()
        .first()
    )

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found.",
        )

    ride = booking.ride

    if not ride:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ride information is unavailable.",
        )

    if ride.driver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Only the assigned driver can "
                "reject this booking."
            ),
        )

    if booking.status != booking_models.BookingStatusEnum.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Only a PENDING booking can be rejected."
            ),
        )

    _ensure_no_existing_cancellation(
        db,
        booking.id,
    )

    fare_kobo = _fare_to_kobo(booking.fare)

    cancellation = booking_models.BookingCancellation(
        booking_id=booking.id,
        cancelled_by_id=current_user.id,
        cancellation_type=(
            booking_models.CancellationTypeEnum.DRIVER
        ),
        reason=(
            f"Driver rejected booking: "
            f"{payload.reason}"
        ),
        original_fare_kobo=fare_kobo,
        penalty_kobo=0,
        passenger_refund_kobo=fare_kobo,
        passenger_voucher_kobo=0,
        driver_voucher_kobo=0,
        company_share_kobo=0,
        driver_wallet_charge_kobo=0,
        refund_required=True,
        refund_requested=False,
        refund_status=(
            booking_models.CancellationRefundStatusEnum.REQUIRED
        ),
    )

    db.add(cancellation)

    booking.status = (
        booking_models.BookingStatusEnum.CANCELLED
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(booking)

    booking = (
        db.query(booking_models.Booking)
        .options(
            joinedload(
                booking_models.Booking.passenger
            ),
            joinedload(
                booking_models.Booking.ride
            ),
        )
        .filter(
            booking_models.Booking.id == booking_id
        )
        .first()
    )

    if booking:
        _send_driver_rejection_notification(
            booking=booking,
            driver=current_user,
        )

    return booking


# ============================================================
# 7. START TRIP
# POST /bookings/{booking_id}/start-trip
# ============================================================


@router.post(
    "/{booking_id}/start-trip",
    response_model=booking_schemas.BookingOut,
)
def start_trip(
    booking_id: int,
    payload: booking_schemas.BookingTripAction = None,
    db: Session = Depends(get_db),
    current_user: user_models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Driver starts a confirmed trip.
    """

    booking = (
        db.query(booking_models.Booking)
        .filter(
            booking_models.Booking.id == booking_id
        )
        .with_for_update()
        .first()
    )

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found.",
        )

    if not booking.ride:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ride information is unavailable.",
        )

    if booking.ride.driver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Only the assigned driver can "
                "start this trip."
            ),
        )

    if booking.status != booking_models.BookingStatusEnum.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Booking must be CONFIRMED before "
                "starting the trip."
            ),
        )

    booking.status = (
        booking_models.BookingStatusEnum.TRIP_STARTED
    )

    booking.trip_started_at = _utc_now()

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(booking)

    return booking


# ============================================================
# 8. COMPLETE TRIP
# POST /bookings/{booking_id}/complete-trip
# ============================================================


@router.post(
    "/{booking_id}/complete-trip",
    response_model=booking_schemas.BookingOut,
)
def complete_trip(
    booking_id: int,
    payload: booking_schemas.BookingTripAction = None,
    db: Session = Depends(get_db),
    current_user: user_models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Driver completes a started trip.

    The payment/settlement worker should later use the completion
    timestamp to determine when held funds become releasable.
    """

    booking = (
        db.query(booking_models.Booking)
        .filter(
            booking_models.Booking.id == booking_id
        )
        .with_for_update()
        .first()
    )

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found.",
        )

    if not booking.ride:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ride information is unavailable.",
        )

    if booking.ride.driver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Only the assigned driver can "
                "complete this trip."
            ),
        )

    if booking.status != booking_models.BookingStatusEnum.TRIP_STARTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Trip must be TRIP_STARTED before "
                "completion."
            ),
        )

    completed_at = _utc_now()

    booking.status = (
        booking_models.BookingStatusEnum.TRIP_COMPLETED
    )

    booking.trip_completed_at = completed_at

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(booking)

    return booking


# ============================================================
# 9. PASSENGER CANCELLATION
# POST /bookings/{booking_id}/cancel/passenger
# ============================================================


@router.post(
    "/{booking_id}/cancel/passenger",
    response_model=booking_schemas.BookingCancellationOut,
)
def cancel_booking_as_passenger(
    booking_id: int,
    payload: booking_schemas.BookingCancellationRequest = None,
    db: Session = Depends(get_db),
    current_user: user_models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Passenger cancellation policy:

        Original fare
            ↓
        10% cancellation penalty
            ↓
        5% of fare -> driver voucher
        5% of fare -> company share
        90% of fare -> passenger refund entitlement

    The passenger must separately apply for the refund.

    The provider refund itself is NOT executed by this endpoint.
    """

    booking = (
        db.query(booking_models.Booking)
        .filter(
            booking_models.Booking.id == booking_id
        )
        .with_for_update()
        .first()
    )

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found.",
        )

    if booking.passenger_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only cancel your own booking.",
        )

    if not _booking_can_be_cancelled(booking):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This booking cannot be cancelled in its "
                f"current status: {booking.status.value}."
            ),
        )

    # 48-hour rule.
    ensure_cancellation_window_is_open(booking)

    # Prevent duplicate cancellation.
    _ensure_no_existing_cancellation(
        db,
        booking.id,
    )

    # --------------------------------------------------------
    # FINANCIAL CALCULATION
    # --------------------------------------------------------

    fare_kobo = _fare_to_kobo(booking.fare)

    penalty_kobo = (
        fare_kobo
        * CANCELLATION_PENALTY_PERCENT
        // 100
    )

    passenger_refund_kobo = (
        fare_kobo - penalty_kobo
    )

    driver_voucher_kobo = (
        penalty_kobo
        * VOUCHER_PERCENT_OF_PENALTY
        // 100
    )

    company_share_kobo = (
        penalty_kobo
        - driver_voucher_kobo
    )

    # --------------------------------------------------------
    # CANCELLATION RECORD
    # --------------------------------------------------------

    cancellation = booking_models.BookingCancellation(
        booking_id=booking.id,
        cancelled_by_id=current_user.id,
        cancellation_type=(
            booking_models.CancellationTypeEnum.PASSENGER
        ),
        reason=(
            payload.reason
            if payload
            else None
        ),
        original_fare_kobo=fare_kobo,
        penalty_kobo=penalty_kobo,
        passenger_refund_kobo=passenger_refund_kobo,
        passenger_voucher_kobo=0,
        driver_voucher_kobo=driver_voucher_kobo,
        company_share_kobo=company_share_kobo,
        driver_wallet_charge_kobo=0,
        refund_required=True,
        refund_requested=False,
        refund_status=(
            booking_models.CancellationRefundStatusEnum.REQUIRED
        ),
    )

    db.add(cancellation)

    # --------------------------------------------------------
    # CANCEL BOOKING
    # --------------------------------------------------------

    booking.status = (
        booking_models.BookingStatusEnum.CANCELLED
    )

    db.flush()

    # --------------------------------------------------------
    # DRIVER VOUCHER
    # --------------------------------------------------------

    driver_id = booking.ride.driver_id

    driver_voucher = booking_models.RideVoucher(
        user_id=driver_id,
        booking_id=booking.id,
        amount_kobo=driver_voucher_kobo,
        used_kobo=0,
        reason="Passenger cancellation compensation",
    )

    db.add(driver_voucher)

    # --------------------------------------------------------
    # COMMIT ATOMIC TRANSACTION
    # --------------------------------------------------------

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(cancellation)

    return {
        "message": (
            "Booking cancelled successfully. "
            "Please apply for your refund."
        ),
        "booking_id": booking.id,
        "cancellation_type": (
            booking_models.CancellationTypeEnum.PASSENGER
        ),
        "original_fare_kobo": fare_kobo,
        "penalty_kobo": penalty_kobo,
        "passenger_refund_kobo": passenger_refund_kobo,
        "passenger_voucher_kobo": 0,
        "driver_voucher_kobo": driver_voucher_kobo,
        "company_share_kobo": company_share_kobo,
        "driver_wallet_charge_kobo": 0,
        "refund_required": True,
        "refund_requested": False,
        "refund_status": (
            booking_models.CancellationRefundStatusEnum.REQUIRED
        ),
    }


# ============================================================
# 10. DRIVER CANCELLATION
# POST /bookings/{booking_id}/cancel/driver
# ============================================================


@router.post(
    "/{booking_id}/cancel/driver",
    response_model=booking_schemas.BookingCancellationOut,
)
def cancel_booking_as_driver(
    booking_id: int,
    payload: booking_schemas.BookingCancellationRequest = None,
    db: Session = Depends(get_db),
    current_user: user_models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Driver cancellation policy:

        Original fare
            ↓
        10% driver cancellation penalty
            ↓
        5% passenger voucher
        5% company share
        100% passenger refund

    The 10% penalty is debited from the driver's AVAILABLE wallet.

    The wallet debit and cancellation record are committed together.
    """

    booking = (
        db.query(booking_models.Booking)
        .filter(
            booking_models.Booking.id == booking_id
        )
        .with_for_update()
        .first()
    )

    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found.",
        )

    if not booking.ride:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ride information is unavailable.",
        )

    # --------------------------------------------------------
    # DRIVER AUTHORIZATION
    # --------------------------------------------------------

    if booking.ride.driver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Only the assigned driver can "
                "cancel this booking."
            ),
        )

    if not _booking_can_be_cancelled(booking):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This booking cannot be cancelled in its "
                f"current status: {booking.status.value}."
            ),
        )

    # --------------------------------------------------------
    # 48-HOUR RULE
    # --------------------------------------------------------

    ensure_cancellation_window_is_open(booking)

    # --------------------------------------------------------
    # DUPLICATE CANCELLATION
    # --------------------------------------------------------

    _ensure_no_existing_cancellation(
        db,
        booking.id,
    )

    # --------------------------------------------------------
    # FINANCIAL CALCULATION
    # --------------------------------------------------------

    fare_kobo = _fare_to_kobo(booking.fare)

    penalty_kobo = (
        fare_kobo
        * CANCELLATION_PENALTY_PERCENT
        // 100
    )

    passenger_voucher_kobo = (
        penalty_kobo
        * VOUCHER_PERCENT_OF_PENALTY
        // 100
    )

    company_share_kobo = (
        penalty_kobo
        - passenger_voucher_kobo
    )

    # Passenger receives full refund.
    passenger_refund_kobo = fare_kobo

    # --------------------------------------------------------
    # PAYMENT WALLET SERVICE
    # --------------------------------------------------------

    from app.payments import (
        models as payment_models,
        services as payment_services,
    )

    # Lock driver's wallet before checking/debiting it.
    wallet = (
        db.query(payment_models.Wallet)
        .filter(
            payment_models.Wallet.user_id
            == current_user.id
        )
        .with_for_update()
        .first()
    )

    if wallet is None:
        wallet = payment_services.get_or_create_wallet(
            db,
            current_user.id,
        )

    if wallet.available_balance_kobo < penalty_kobo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Insufficient available wallet balance "
                "to cover the driver cancellation penalty."
            ),
        )

    # --------------------------------------------------------
    # CANCELLATION RECORD
    # --------------------------------------------------------

    cancellation = booking_models.BookingCancellation(
        booking_id=booking.id,
        cancelled_by_id=current_user.id,
        cancellation_type=(
            booking_models.CancellationTypeEnum.DRIVER
        ),
        reason=(
            payload.reason
            if payload
            else None
        ),
        original_fare_kobo=fare_kobo,
        penalty_kobo=penalty_kobo,
        passenger_refund_kobo=passenger_refund_kobo,
        passenger_voucher_kobo=passenger_voucher_kobo,
        driver_voucher_kobo=0,
        company_share_kobo=company_share_kobo,
        driver_wallet_charge_kobo=penalty_kobo,
        refund_required=True,
        refund_requested=False,
        refund_status=(
            booking_models.CancellationRefundStatusEnum.REQUIRED
        ),
    )

    db.add(cancellation)

    # --------------------------------------------------------
    # CANCEL BOOKING
    # --------------------------------------------------------

    booking.status = (
        booking_models.BookingStatusEnum.CANCELLED
    )

    db.flush()

    # --------------------------------------------------------
    # DRIVER WALLET DEBIT
    # --------------------------------------------------------

    payment_services.record_ledger_entry(
        db,
        user_id=current_user.id,
        transaction_type=(
            payment_models.TransactionTypeEnum.adjustment
        ),
        direction="debit",
        amount_kobo=penalty_kobo,
        balance_bucket=(
            payment_models.BalanceBucketEnum.available
        ),
        description=(
            "Driver cancellation penalty "
            f"for booking {booking.id}"
        ),
        booking_id=booking.id,
    )

    # --------------------------------------------------------
    # PASSENGER VOUCHER
    # --------------------------------------------------------

    passenger_voucher = booking_models.RideVoucher(
        user_id=booking.passenger_id,
        booking_id=booking.id,
        amount_kobo=passenger_voucher_kobo,
        used_kobo=0,
        reason="Driver cancellation compensation",
    )

    db.add(passenger_voucher)

    # --------------------------------------------------------
    # COMMIT EVERYTHING TOGETHER
    # --------------------------------------------------------

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(cancellation)

    return {
        "message": (
            "Ride cancelled by driver. "
            "Passenger is entitled to a full refund."
        ),
        "booking_id": booking.id,
        "cancellation_type": (
            booking_models.CancellationTypeEnum.DRIVER
        ),
        "original_fare_kobo": fare_kobo,
        "penalty_kobo": penalty_kobo,
        "passenger_refund_kobo": passenger_refund_kobo,
        "passenger_voucher_kobo": passenger_voucher_kobo,
        "driver_voucher_kobo": 0,
        "company_share_kobo": company_share_kobo,
        "driver_wallet_charge_kobo": penalty_kobo,
        "refund_required": True,
        "refund_requested": False,
        "refund_status": (
            booking_models.CancellationRefundStatusEnum.REQUIRED
        ),
    }
