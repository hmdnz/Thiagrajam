"""
Create passenger bookings against the demo ride schedule.

Bookings are spread across the 100-day ride window. Each ride occurrence gets
1-3 passenger bookings when seats permit, while preventing a passenger from
booking their own driver's ride.

This is aligned with the current Booking model in app/bookings/models.py:
    passenger_id, ride_id, car_id, travel_date, seats_booked, fare, status
"""

import random
from datetime import datetime, timezone
from decimal import Decimal

from app.database import SessionLocal
from app.models import User
from app.rides.models import Ride, RideOccurrence
from app.bookings.models import Booking, BookingStatusEnum

random.seed(20261012)

STATUS_WEIGHTS = [
    (BookingStatusEnum.CONFIRMED, 0.70),
    (BookingStatusEnum.PENDING, 0.20),
    (BookingStatusEnum.CANCELLED, 0.10),
]


def choose_status():
    """Return a booking status using a realistic demo distribution."""
    statuses = [status for status, _ in STATUS_WEIGHTS]
    weights = [weight for _, weight in STATUS_WEIGHTS]
    return random.choices(statuses, weights=weights, k=1)[0]


def seed_bookings() -> None:
    """Create passenger bookings for available demo ride occurrences."""
    db = SessionLocal()
    try:
        passengers = (
            db.query(User)
            .filter(
                 User.email.like("p-%@rideapp.ng"),
                 User.is_driver.is_(False),
            )
            .order_by(User.email)
            .all()
        )

        if not passengers:
            print("No demo passengers found. Run seed_users.py first.")
            return

        occurrences = (
            db.query(RideOccurrence)
            .filter(
                RideOccurrence.is_cancelled.is_(False),
                RideOccurrence.seats_remaining > 0,
            )
            .order_by(RideOccurrence.date, RideOccurrence.id)
            .all()
        )

        if not occurrences:
            print("No ride occurrences found. Run seed_rides.py first.")
            return

        bookings_created = 0

        for occurrence in occurrences:
            ride = db.query(Ride).filter(Ride.id == occurrence.ride_id).first()
            if not ride:
                continue

            # Never allow the driver of a ride to book that same ride.
            eligible = [p for p in passengers if p.id != ride.driver_id]
            if not eligible:
                continue

            # Avoid duplicate seed bookings if this script is re-run.
            already_booked_ids = {
                row.passenger_id
                for row in db.query(Booking)
                .filter(Booking.ride_id == ride.id, Booking.travel_date == occurrence.date)
                .all()
            }
            eligible = [p for p in eligible if p.id not in already_booked_ids]
            if not eligible:
                continue

            # Usually create 1-3 bookings per ride, limited by available seats.
            requested = random.randint(1, 3)
            selected = random.sample(eligible, min(requested, len(eligible)))
            seats_left = occurrence.seats_remaining

            for passenger in selected:
                if seats_left <= 0:
                    break

                seats_booked = random.randint(1, min(2, seats_left))
                fare = Decimal(str(ride.price_per_seat)) * Decimal(seats_booked)
                status = choose_status()

                booking = Booking(
                    passenger_id=passenger.id,
                    ride_id=ride.id,
                    car_id=ride.car_id,
                    travel_date=occurrence.date,
                    seats_booked=seats_booked,
                    fare=fare,
                    status=status,
                    created_at=datetime.now(timezone.utc),
                )
                db.add(booking)
                bookings_created += 1

                # Only pending/confirmed bookings consume seats.
                if status in (BookingStatusEnum.PENDING, BookingStatusEnum.CONFIRMED):
                    seats_left -= seats_booked

            occurrence.seats_remaining = seats_left

        db.commit()
        print(f"Created {bookings_created} demo passenger bookings across the 100-day schedule.")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_bookings()
