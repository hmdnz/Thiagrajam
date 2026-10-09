"""
Create one realistic car for every demo driver.

Aligned with the current app/cars/models.py Car model, where the foreign key
is `driver_id` (not user_id or owner_id).
"""

import random

from app.database import SessionLocal, engine
from app.models import User
from app.cars.models import Car, CarPhoto

random.seed(20261010)

SAMPLE_CARS = [
    ("Toyota", "Corolla", 4),
    ("Toyota", "Camry", 4),
    ("Toyota", "Highlander", 6),
    ("Toyota", "Sienna", 7),
    ("Honda", "Accord", 4),
    ("Honda", "CR-V", 4),
    ("Lexus", "RX 350", 4),
    ("Nissan", "Altima", 4),
    ("Hyundai", "Elantra", 4),
    ("Hyundai", "Tucson", 4),
    ("Kia", "Sportage", 4),
    ("Mercedes-Benz", "C-Class", 4),
    ("GAC", "GS4", 4),
    ("Geely", "Coolray", 4),
    ("Chery", "Tiggo 7 Pro", 4),
]

COLORS = ["Silver", "Black", "White", "Dark Grey", "Navy Blue", "Wine Red", "Gold"]
PLATE_PREFIXES = [
    "KNO", "KAD", "ABJ", "LAG", "PHC", "GOM", "BAU", "ENU", "BEN", "IMO",
]


def seed_driver_cars() -> None:
    """Create exactly one car for each demo driver."""
    db = SessionLocal()
    try:
        print(f"Connecting to database: {engine.url}")

        drivers = (
            db.query(User)
            .filter(User.email.like("demo.driver.%@rideapp.ng"), User.is_driver.is_(True))
            .order_by(User.email)
            .all()
        )

        if not drivers:
            print("No demo drivers found. Run seed_users.py first.")
            return

        cars_created = 0

        for index, driver in enumerate(drivers, start=1):
            # Make the script safe to re-run.
            existing_car = db.query(Car).filter(Car.driver_id == driver.id).first()
            if existing_car:
                continue

            make, model, capacity = random.choice(SAMPLE_CARS)
            plate = f"{random.choice(PLATE_PREFIXES)}-{100 + index:03d}-{chr(65 + (index % 26))}{chr(65 + ((index + 5) % 26))}"

            car = Car(
                driver_id=driver.id,
                make=make,
                model=model,
                year=random.randint(2015, 2025),
                color=random.choice(COLORS),
                plate_number=plate,
                capacity=capacity,
                is_tinted=random.choice([True, False]),
                has_wifi=random.choice([True, False]),
                has_air_conditioning=True,
                has_power_outlets=random.choice([True, False]),
                smoking_allowed=False,
                pets_allowed=driver.pets_preference is not None and driver.pets_preference.value != "No pets allowed",
                wheelchair_accessible=random.choice([False, False, True]),
                is_suspended=False,
            )
            db.add(car)
            db.flush()

            # Add two demo photos so the car records look complete in the UI.
            db.add_all([
                CarPhoto(
                    car_id=car.id,
                    photo_url=f"https://placehold.co/800x600?text={make}+{model}+Exterior",
                ),
                CarPhoto(
                    car_id=car.id,
                    photo_url=f"https://placehold.co/800x600?text={make}+{model}+Interior",
                ),
            ])
            cars_created += 1

        db.commit()
        print(f"Created {cars_created} cars for demo drivers.")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_driver_cars()
