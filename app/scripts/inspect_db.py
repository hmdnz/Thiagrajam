"""
scripts/inspect_db.py

Prints the current state of users, cars, rides, bookings, and
payments so you know what you can test with.

Run from the project root:
    python scripts\inspect_db.py
"""

# --- Path bootstrap: make `app` importable when this file is run directly ---
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# ---------------------------------------------------------------------------

from app.database import SessionLocal
from app import models
from app.cars import models as car_models
from app.rides import models as ride_models
from app.bookings import models as booking_models
from app.payments import models as payment_models


def hr(title):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def s(value, width=None, default="<none>"):
    """Safe string formatter — never crashes on None."""
    text = default if value is None else str(value)
    return f"{text:<{width}}" if width else text


def main():
    db = SessionLocal()
    try:
        # ---------------- USERS ----------------
        hr("USERS")
        users = db.query(models.User).all()
        if not users:
            print("  (no users)")
        for u in users:
            print(
                f"  id={s(u.id, 4)} "
                f"email={s(u.email, 35)} "
                f"admin={s(getattr(u, 'is_admin', '?'))} "
                f"profile={s(getattr(u, 'profile_completed', '?'))} "
                f"nin={s(getattr(u, 'nin_verified', '?'))} "
                f"licence={s(getattr(u, 'licence_verified', '?'))} "
                f"can_book={s(getattr(u, 'can_book_rides', '?'))} "
                f"can_offer={s(getattr(u, 'can_offer_rides', '?'))}"
            )

        # ---------------- CARS ----------------
        hr("CARS")
        cars = db.query(car_models.Car).all()
        if not cars:
            print("  (no cars)")
        for c in cars:
            print(
                f"  id={s(c.id, 4)} "
                f"driver_id={s(c.driver_id, 4)} "
                f"{s(c.make)} {s(c.model)} {s(c.year)} ({s(c.color)})"
            )

        # ---------------- RIDES ----------------
        hr("RIDES")
        rides = db.query(ride_models.Ride).all()
        if not rides:
            print("  (no rides)")
        for r in rides:
            occs = [str(o.date) for o in r.occurrences]
            print(
                f"  id={s(r.id, 4)} "
                f"driver_id={s(r.driver_id, 4)} "
                f"car_id={s(r.car_id, 4)} "
                f"{s(r.pickup_location)} -> {s(r.dropoff_location)} "
                f"@ {s(r.pickup_time)} | "
                f"N{s(r.price_per_seat)} | "
                f"active={s(r.is_active)} | "
                f"instant={s(r.instant_booking)} | "
                f"dates={occs}"
            )

        # ---------------- BOOKINGS ----------------
        hr("BOOKINGS")
        bookings = db.query(booking_models.Booking).all()
        if not bookings:
            print("  (no bookings)")
        for b in bookings:
            print(
                f"  id={s(b.id, 4)} "
                f"passenger_id={s(b.passenger_id, 4)} "
                f"ride_id={s(b.ride_id, 4)} "
                f"date={s(b.travel_date)} "
                f"seats={s(b.seats_booked)} "
                f"fare={s(b.fare)} "
                f"status={s(b.status)}"
            )

        # ---------------- PAYMENTS ----------------
        hr("PAYMENTS")
        payments = db.query(payment_models.Payment).all()
        if not payments:
            print("  (no payments)")
        for p in payments:
            print(
                f"  id={s(p.id, 4)} "
                f"user_id={s(p.user_id, 4)} "
                f"booking_id={s(p.booking_id)} "
                f"ref={s(p.transaction_ref)} "
                f"amount_kobo={s(p.amount_kobo)} "
                f"status={s(p.status)} "
                f"raw={s(p.raw_status)}"
            )

    finally:
        db.close()


if __name__ == "__main__":
    main()