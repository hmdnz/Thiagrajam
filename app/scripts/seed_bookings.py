import random
from decimal import Decimal
from datetime import datetime, timezone
from app.database import SessionLocal
from app.rides.models import Ride, RideOccurrence
from app.models import User

# Try importing Booking model from common path locations
try:
    from app.bookings.models import Booking
except ImportError:
    try:
        from app.models import Booking
    except ImportError:
        raise ImportError("Could not locate Booking model. Please check the import path in app/bookings/models.py.")


BOOKING_STATUSES = ["confirmed", "pending", "cancelled"]
# Status distribution weights: 70% confirmed, 20% pending, 10% cancelled
STATUS_WEIGHTS = [0.70, 0.20, 0.10]


def seed_bookings():
    db = SessionLocal()
    try:
        # 1. Fetch non-driver passengers
        passengers = db.query(User).filter(
            User.is_driver == False,
            User.is_active == True
        ).all()

        if not passengers:
            print("⚠️ No dedicated non-driver passengers found. Fetching all active users...")
            passengers = db.query(User).filter(User.is_active == True).all()

        if not passengers:
            print("❌ No active users found in the database. Run user seeder first.")
            return

        passenger_ids = [p.id for p in passengers]
        print(f" Found {len(passenger_ids)} prospective passengers for booking creation.")

        # 2. Fetch available Ride Occurrences that have seats remaining
        occurrences = db.query(RideOccurrence).filter(
            RideOccurrence.seats_remaining > 0
        ).all()

        if not occurrences:
            print("❌ No active ride occurrences with available seats found. Run ride seeder first.")
            return

        print(f" Found {len(occurrences)} active ride occurrences with open seats.")

        # Check for optional pricing columns
        has_fare = hasattr(Booking, "fare")
        has_total_price = hasattr(Booking, "total_price")
        has_price = hasattr(Booking, "price")

        bookings_created = 0

        # 3. Create passenger bookings linked to rides/occurrences
        for occurrence in occurrences:
            # Fetch parent ride details
            ride = db.query(Ride).filter(Ride.id == occurrence.ride_id).first()
            if not ride:
                continue

            seats_left_for_occurrence = occurrence.seats_remaining

            # Select passengers who aren't the driver of this ride
            eligible_passengers = [pid for pid in passenger_ids if pid != ride.driver_id]
            if not eligible_passengers:
                continue

            # Randomize how many passengers book on this date
            num_bookings_for_this_date = random.randint(1, min(len(eligible_passengers), 2))
            selected_passengers = random.sample(eligible_passengers, num_bookings_for_this_date)

            for passenger_id in selected_passengers:
                if seats_left_for_occurrence <= 0:
                    break

                seats_booked = random.randint(1, min(2, seats_left_for_occurrence))
                calculated_fare = Decimal(str(ride.price_per_seat)) * Decimal(seats_booked)
                status = random.choices(BOOKING_STATUSES, weights=STATUS_WEIGHTS)[0]

                # Match exact schema requirements identified from database trace
                booking_kwargs = {
                    "ride_id": ride.id,
                    "passenger_id": passenger_id,
                    "car_id": ride.car_id,
                    "travel_date": occurrence.date,
                    "seats_booked": seats_booked,
                    "status": status,
                    "created_at": datetime.now(timezone.utc)
                }

                # Attach optional price fields if they exist on the model
                if has_fare:
                    booking_kwargs["fare"] = calculated_fare
                elif has_total_price:
                    booking_kwargs["total_price"] = calculated_fare
                elif has_price:
                    booking_kwargs["price"] = calculated_fare

                booking = Booking(**booking_kwargs)
                db.add(booking)
                bookings_created += 1

                # Deduct seats if the booking is active
                if status in ["confirmed", "pending"]:
                    seats_left_for_occurrence -= seats_booked

            # Update occurrence seats remaining
            occurrence.seats_remaining = seats_left_for_occurrence

        db.commit()
        print(f" Successfully created {bookings_created} passenger bookings across ride occurrences!")

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding bookings: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_bookings()