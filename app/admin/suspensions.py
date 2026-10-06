"""
app/admin/suspensions.py

Admin suspension / reinstatement.

POST /admin/suspensions/passengers/{user_id}/suspend | reinstate
POST /admin/suspensions/drivers/{user_id}/suspend    | reinstate
POST /admin/suspensions/cars/{car_id}/suspend        | reinstate

Passenger suspension -> cannot book, pay, or ride; upcoming bookings cancelled.
Driver suspension    -> cannot publish rides, confirm/start trips, or request
                        payouts (pending payouts cannot be approved); rides are
                        hidden from search; upcoming bookings on their rides
                        are cancelled.
Car suspension       -> car cannot be used for rides; rides on it are hidden;
                        upcoming bookings on it are cancelled.

Cancelled bookings with a successful payment get a PENDING refund for an admin
to review (see app/admin/suspension_effects.py). Trips already started are not
cancelled; they are counted in `trips_in_progress`.

The three suspensions are independent. Suspending does not touch can_book_rides
/ can_offer_rides, so reinstating restores the previous eligibility. Reinstating
does NOT restore cancelled bookings.
"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models
from app.admin import models as admin_models
from app.admin import schemas as admin_schemas
from app.admin.permissions import SUSPENSION_ROLES, require_roles
from app.admin.suspension_effects import apply_to_bookings
from app.cars import models as car_models
from app.database import get_db
from app.rides import models as ride_models

router = APIRouter(
    prefix="/admin/suspensions",
    tags=["Admin - Suspensions"],
)


def _now():
    return datetime.now(timezone.utc)


def _audit(db, admin, action, entity, target_id, reason):
    db.add(
        admin_models.AdminAuditLog(
            admin_id=admin.id,
            action=action,
            target_entity=entity,
            target_id=str(target_id),
            reason=reason,
        )
    )


def _get_user_or_404(db: Session, user_id: UUID) -> models.User:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    return user


def _get_car_or_404(db: Session, car_id: int) -> car_models.Car:
    car = db.query(car_models.Car).filter(car_models.Car.id == car_id).first()
    if not car:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Car not found.")
    return car


def _no_admins(user: models.User):
    if user.is_admin:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Admin accounts cannot be suspended here.",
        )


def _active_rides(db: Session, **filters) -> int:
    return (
        db.query(ride_models.Ride)
        .filter_by(is_active=True, **filters)
        .count()
    )


# ============================================================
# PASSENGER
# ============================================================

@router.post(
    "/passengers/{user_id}/suspend",
    response_model=admin_schemas.SuspensionResultOut,
)
def suspend_passenger(
    user_id: UUID,
    payload: admin_schemas.SuspensionPayload,
    db: Session = Depends(get_db),
    admin=Depends(require_roles(*SUSPENSION_ROLES)),
):
    """Suspended passengers cannot book or pay for rides."""
    user = _get_user_or_404(db, user_id)
    _no_admins(user)
    if user.is_suspended:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Passenger is already suspended."
        )

    user.is_suspended = True
    user.suspension_reason = payload.reason
    user.suspended_at = _now()
    fx = apply_to_bookings(
        db, passenger_id=user.id, reason=f"passenger suspended - {payload.reason}"
    )
    _audit(
        db, admin, "SUSPEND_PASSENGER", "users", user.id,
        f"{payload.reason} | {fx.summary()}",
    )
    db.commit()

    return admin_schemas.SuspensionResultOut(
        target="passenger",
        target_id=str(user.id),
        is_suspended=True,
        message="Passenger suspended. They can no longer book or ride. " + fx.summary(),
        bookings_cancelled=fx.bookings_cancelled,
        refunds_queued=fx.refunds_queued,
        trips_in_progress=fx.trips_in_progress,
    )


@router.post(
    "/passengers/{user_id}/reinstate",
    response_model=admin_schemas.SuspensionResultOut,
)
def reinstate_passenger(
    user_id: UUID,
    payload: admin_schemas.ReinstatePayload,
    db: Session = Depends(get_db),
    admin=Depends(require_roles(*SUSPENSION_ROLES)),
):
    user = _get_user_or_404(db, user_id)
    if not user.is_suspended:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Passenger is not suspended."
        )

    user.is_suspended = False
    user.suspension_reason = None
    user.suspended_at = None
    _audit(
        db, admin, "REINSTATE_PASSENGER", "users", user.id,
        payload.reason or "Suspension lifted.",
    )
    db.commit()

    return admin_schemas.SuspensionResultOut(
        target="passenger",
        target_id=str(user.id),
        is_suspended=False,
        message="Passenger reinstated.",
    )


# ============================================================
# DRIVER
# ============================================================

@router.post(
    "/drivers/{user_id}/suspend",
    response_model=admin_schemas.SuspensionResultOut,
)
def suspend_driver(
    user_id: UUID,
    payload: admin_schemas.SuspensionPayload,
    db: Session = Depends(get_db),
    admin=Depends(require_roles(*SUSPENSION_ROLES)),
):
    """Suspended drivers cannot publish rides, and their rides are
    hidden from search and cannot be booked."""
    user = _get_user_or_404(db, user_id)
    _no_admins(user)
    if not (user.is_driver or user.driver_profile):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "This user is not a driver."
        )
    if user.is_driver_suspended:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Driver is already suspended."
        )

    user.is_driver_suspended = True
    user.driver_suspension_reason = payload.reason
    user.driver_suspended_at = _now()
    fx = apply_to_bookings(
        db, driver_id=user.id, reason=f"driver suspended - {payload.reason}"
    )
    _audit(
        db, admin, "SUSPEND_DRIVER", "drivers", user.id,
        f"{payload.reason} | {fx.summary()}",
    )
    db.commit()

    return admin_schemas.SuspensionResultOut(
        target="driver",
        target_id=str(user.id),
        is_suspended=True,
        message="Driver suspended. They can no longer publish rides, and payouts are on hold. " + fx.summary(),
        rides_affected=_active_rides(db, driver_id=user.id),
        bookings_cancelled=fx.bookings_cancelled,
        refunds_queued=fx.refunds_queued,
        trips_in_progress=fx.trips_in_progress,
    )


@router.post(
    "/drivers/{user_id}/reinstate",
    response_model=admin_schemas.SuspensionResultOut,
)
def reinstate_driver(
    user_id: UUID,
    payload: admin_schemas.ReinstatePayload,
    db: Session = Depends(get_db),
    admin=Depends(require_roles(*SUSPENSION_ROLES)),
):
    user = _get_user_or_404(db, user_id)
    if not user.is_driver_suspended:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Driver is not suspended."
        )

    user.is_driver_suspended = False
    user.driver_suspension_reason = None
    user.driver_suspended_at = None
    _audit(
        db, admin, "REINSTATE_DRIVER", "drivers", user.id,
        payload.reason or "Suspension lifted.",
    )
    db.commit()

    return admin_schemas.SuspensionResultOut(
        target="driver",
        target_id=str(user.id),
        is_suspended=False,
        message="Driver reinstated.",
        rides_affected=_active_rides(db, driver_id=user.id),
    )


# ============================================================
# CAR
# ============================================================

@router.post(
    "/cars/{car_id}/suspend",
    response_model=admin_schemas.SuspensionResultOut,
)
def suspend_car(
    car_id: int,
    payload: admin_schemas.SuspensionPayload,
    db: Session = Depends(get_db),
    admin=Depends(require_roles(*SUSPENSION_ROLES)),
):
    """A suspended car cannot be used to publish rides, and rides on it
    are hidden from search and cannot be booked."""
    car = _get_car_or_404(db, car_id)
    if car.is_suspended:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Car is already suspended."
        )

    car.is_suspended = True
    car.suspension_reason = payload.reason
    car.suspended_at = _now()
    fx = apply_to_bookings(
        db, car_id=car.id, reason=f"car suspended - {payload.reason}"
    )
    _audit(
        db, admin, "SUSPEND_CAR", "cars", car.id,
        f"{payload.reason} | {fx.summary()}",
    )
    db.commit()

    return admin_schemas.SuspensionResultOut(
        target="car",
        target_id=str(car.id),
        is_suspended=True,
        message="Car suspended. It can no longer be used for rides. " + fx.summary(),
        rides_affected=_active_rides(db, car_id=car.id),
        bookings_cancelled=fx.bookings_cancelled,
        refunds_queued=fx.refunds_queued,
        trips_in_progress=fx.trips_in_progress,
    )


@router.post(
    "/cars/{car_id}/reinstate",
    response_model=admin_schemas.SuspensionResultOut,
)
def reinstate_car(
    car_id: int,
    payload: admin_schemas.ReinstatePayload,
    db: Session = Depends(get_db),
    admin=Depends(require_roles(*SUSPENSION_ROLES)),
):
    car = _get_car_or_404(db, car_id)
    if not car.is_suspended:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Car is not suspended."
        )

    car.is_suspended = False
    car.suspension_reason = None
    car.suspended_at = None
    _audit(
        db, admin, "REINSTATE_CAR", "cars", car.id,
        payload.reason or "Suspension lifted.",
    )
    db.commit()

    return admin_schemas.SuspensionResultOut(
        target="car",
        target_id=str(car.id),
        is_suspended=False,
        message="Car reinstated.",
        rides_affected=_active_rides(db, car_id=car.id),
    )
