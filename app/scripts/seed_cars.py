# seed_cars.py
import random
import sys
from os.path import abspath, dirname

# Ensure the root directory is in the import path
sys.path.append(dirname(abspath(__file__)))

# Import database session
from app.database import SessionLocal

# Import models
from app.models import User
from app.cars.models import Car, CarPhoto

SAMPLE_CARS = [
    {"make": "Toyota", "model": "Corolla", "year": 2018, "color": "Silver", "capacity": 4},
    {"make": "Honda", "model": "Civic", "year": 2020, "color": "Black", "capacity": 4},
    {"make": "Toyota", "model": "Camry", "year": 2019, "color": "White", "capacity": 4},
    {"make": "Hyundai", "model": "Elantra", "year": 2021, "color": "Blue", "capacity": 4},
    {"make": "Kia", "model": "Optima", "year": 2017, "color": "Grey", "capacity": 4},
    {"make": "Mercedes-Benz", "model": "C-Class", "year": 2019, "color": "Black", "capacity": 4},
    {"make": "Ford", "model": "Focus", "year": 2020, "color": "White", "capacity": 5},
    {"make": "Nissan", "model": "Altima", "year": 2018, "color": "Blue", "capacity": 5},
]

PLATE_PREFIXES = [
    "KJA", "LND", "GGE", "ABJ", "KMN", "ABJ", "KMN", "KAN", "KNO", "KNS", 
    "ABV", "KMA", "KMB", "KMC", "KMD", "KME", "KMF", "KMG", "KMH", "KMI", 
    "KMJ", "KMK", "KML", "KMM", "KMN"
]

def seed_driver_cars():
    db = SessionLocal()
    try:
        # Filter drivers based on your User model attribute
        drivers = db.query(User).filter(User.role == "driver").all()

        if not drivers:
            print("No drivers found to assign vehicles.")
            return

        cars_created = 0

        for driver in drivers:
            # Skip if driver already has a car
            existing_car = db.query(Car).filter(Car.driver_id == driver.id).first()
            if existing_car:
                continue

            spec = random.choice(SAMPLE_CARS)
            plate = f"{random.choice(PLATE_PREFIXES)}-{random.randint(100, 999)}{chr(random.randint(65, 90))}{chr(random.randint(65, 90))}"

            car = Car(
                driver_id=driver.id,
                make=spec["make"],
                model=spec["model"],
                year=spec["year"],
                color=spec["color"],
                plate_number=plate,
                capacity=spec.get("capacity", 4),
                is_tinted=random.choice([True, False]),
                has_wifi=random.choice([True, False]),
                has_air_conditioning=True,
                has_power_outlets=random.choice([True, False]),
                smoking_allowed=False,
                pets_allowed=random.choice([True, False]),
                wheelchair_accessible=False,
            )

            db.add(car)
            db.flush()

            # Add default sample photos
            photo1 = CarPhoto(
                car_id=car.id,
                photo_url=f"https://placeholder.co/600x400?text={car.make}+{car.model}+Exterior"
            )
            photo2 = CarPhoto(
                car_id=car.id,
                photo_url=f"https://placeholder.co/600x400?text={car.make}+{car.model}+Interior"
            )
            db.add_all([photo1, photo2])

            cars_created += 1

        db.commit()
        print(f"✅ Successfully created {cars_created} vehicles for drivers.")

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding cars: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_driver_cars()