"""
app/admin/suspension_effects.py

What happens to EXISTING bookings when a passenger, driver or car is suspended.

* Upcoming bookings that have not started (pending / confirmed, travel date
  today or later) are CANCELLED.
* Every successful payment on a cancelled booking gets a PENDING full refund.
  Nothing is sent to Paystack/Squad automatically - an admin approves or
  rejects it in POST /payments/admin/refunds/{id}/review, which does the
  provider call and the ledger reversal.
* Trips already STARTED are not cancelled (the passenger may be in the car).
  They are reported back as `trips_in_progress` for the admin to follow up.
* Past-dated bookings are left alone.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.bookings import models as booking_models
from app.payments import models as payment_models
from app.payments import services as payment_services
from app.rides import models as ride_models

BS = booking_models.BookingStatusEnum


@dataclass
class SuspensionEffects:
    bookings_cancelled: int = 0
    refunds_queued: int = 0
    trips_in_progress: int = 0

    def summary(self) -> str:
        return (
            f"{self.bookings_cancelled} booking(s) cancelled, "
            f"{self.refunds_queued} refund(s) queued for review, "
            f"{self.trips_in_progress} trip(s) in progress."
        )


def apply_to_bookings(
    db: Session,
    *,
    passenger_id=None,
    driver_id=None,
    car_id: Optional[int] = None,
    reason: str,
) -> SuspensionEffects:
    """Cancel upcoming bookings for exactly one of passenger / driver / car.
    Flushes but does not commit - the caller commits together with the
    suspension flag and the audit entry."""

    assert sum(x is not None for x in (passenger_id, driver_id, car_id)) == 1

    q = db.query(booking_models.Booking)
    if passenger_id is not None:
        q = q.filter(booking_models.Booking.passenger_id == passenger_id)
    elif driver_id is not None:
        q = q.join(
            ride_models.Ride,
            ride_models.Ride.id == booking_models.Booking.ride_id,
        ).filter(ride_models.Ride.driver_id == driver_id)
    else:
        q = q.filter(booking_models.Booking.car_id == car_id)

    effects = SuspensionEffects()
    today = date.today()

    effects.trips_in_progress = q.filter(
        booking_models.Booking.status == BS.TRIP_STARTED
    ).count()

    upcoming = q.filter(
        booking_models.Booking.status.in_([BS.PENDING, BS.CONFIRMED]),
        booking_models.Booking.travel_date >= today,
    ).all()

    for booking in upcoming:
        booking.status = BS.CANCELLED
        effects.bookings_cancelled += 1

        paid = (
            db.query(payment_models.Payment)
            .filter(
                payment_models.Payment.booking_id == booking.id,
                payment_models.Payment.status
                == payment_models.PaymentStatusEnum.success,
            )
            .all()
        )
        for payment in paid:
            if payment_services.queue_cancellation_refund(
                db,
                payment=payment,
                reason=f"Booking {booking.id} cancelled: {reason}",
            ):
                effects.refunds_queued += 1

    db.flush()
    return effects
