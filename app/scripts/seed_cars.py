import random
import sys
from os.path import abspath, dirname

# Ensure the root directory is in the import path
sys.path.append(dirname(dirname(dirname(abspath(__file__)))))

from app.database import SessionLocal, engine
from app.models import User
from app.cars.models import Car, CarPhoto

# ==========================================
# VEHICLE CATALOG (Including Chinese EVs)
# ==========================================
SAMPLE_CARS = [
    # Japanese Classics
    {"make": "Toyota", "model": "Corolla", "capacity": 4},
    {"make": "Toyota", "model": "Camry", "capacity": 4},
    {"make": "Toyota", "model": "RAV4", "capacity": 4},
    {"make": "Toyota", "model": "Highlander", "capacity": 6},
    {"make": "Toyota", "model": "Sienna", "capacity": 7},
    {"make": "Toyota", "model": "Matrix", "capacity": 4},
    {"make": "Honda", "model": "Civic", "capacity": 4},
    {"make": "Honda", "model": "Accord", "capacity": 4},
    {"make": "Honda", "model": "CR-V", "capacity": 4},
    {"make": "Lexus", "model": "ES 350", "capacity": 4},
    {"make": "Lexus", "model": "RX 350", "capacity": 4},
    {"make": "Nissan", "model": "Altima", "capacity": 4},
    {"make": "Nissan", "model": "Sentra", "capacity": 4},
    
    # Korean Options
    {"make": "Hyundai", "model": "Elantra", "capacity": 4},
    {"make": "Hyundai", "model": "Sonata", "capacity": 4},
    {"make": "Hyundai", "model": "Tucson", "capacity": 4},
    {"make": "Kia", "model": "Optima", "capacity": 4},
    {"make": "Kia", "model": "Cerato", "capacity": 4},
    {"make": "Kia", "model": "Sportage", "capacity": 4},

    # German / European
    {"make": "Mercedes-Benz", "model": "C-Class", "capacity": 4},
    {"make": "Mercedes-Benz", "model": "E-Class", "capacity": 4},
    {"make": "Volkswagen", "model": "Passat", "capacity": 4},
    {"make": "Volkswagen", "model": "Golf", "capacity": 4},

    # Chinese EVs & ICE Models
    {"make": "BYD", "model": "Dolphin (EV)", "capacity": 4},
    {"make": "BYD", "model": "Atto 3 (EV)", "capacity": 4},
    {"make": "BYD", "model": "Seal (EV)", "capacity": 4},
    {"make": "GAC", "model": "Aion Y (EV)", "capacity": 4},
    {"make": "GAC", "model": "GS4", "capacity": 4},
    {"make": "GAC", "model": "GA4", "capacity": 4},
    {"make": "Geely", "model": "Coolray", "capacity": 4},
    {"make": "Geely", "model": "Emgrand", "capacity": 4},
    {"make": "Chery", "model": "Tiggo 4 Pro", "capacity": 4},
    {"make": "Chery", "model": "Tiggo 7 Pro", "capacity": 4},
    {"make": "Changan", "model": "Alsvin", "capacity": 4},
    {"make": "Changan", "model": "CS35 Plus", "capacity": 4},
]

CAR_COLORS = [
    "Silver", "Black", "White", "Dark Grey", "Navy Blue", 
    "Wine Red", "Gold", "Champagne", "Pearl White"
]

PLATE_PREFIXES = [
    "KJA", "LND", "GGE", "EKY", "LSD", "EPE", "IKJ", "APP", "AKD", "AGL",
    "ABJ", "RBC", "BWR", "KWL", "PHC", "BGM", "AHO", "NRK", "AGODI", "LUY",
    "KNO", "KMC", "UNW", "KAD", "DKA", "ZAR", "ENU", "NWD", "ASB", "EPR",
    "UWW", "AWK", "ONITSHA", "ABK", "JGB", "TTA", "BEN", "BENIN"
]


def seed_driver_cars():
    db = SessionLocal()
    try:
        print(f"Connecting to database: {engine.url}")

        drivers = db.query(User).filter(User.is_driver == True).all()

        if not drivers:
            print("⚠️ No drivers found. Make sure you ran seed_users.py first!")
            return

        print(f"Found {len(drivers)} drivers. Starting vehicle seeding...")

        cars_created = 0

        for driver in drivers:
            existing_car = db.query(Car).filter(Car.driver_id == driver.id).first()
            if existing_car:
                continue

            spec = random.choice(SAMPLE_CARS)
            
            prefix = random.choice(PLATE_PREFIXES)
            numbers = random.randint(100, 999)
            letters = f"{chr(random.randint(65, 90))}{chr(random.randint(65, 90))}"
            plate = f"{prefix}-{numbers}{letters}"

            # Rely strictly on model defaults and auto-increment PKs
            car = Car(
                driver_id=driver.id,  # UUID matching User.id
                make=spec["make"],
                model=spec["model"],
                year=random.randint(2012, 2024),
                color=random.choice(CAR_COLORS),
                plate_number=plate,
                capacity=spec.get("capacity", 4),
                is_tinted=random.choice([True, False, False]),
                has_wifi=random.choice([True, False, False]),
                has_air_conditioning=True,
                has_power_outlets=random.choice([True, False]),
                smoking_allowed=False,
                pets_allowed=driver.pets_preference.value != "no_pets" if hasattr(driver, 'pets_preference') else False,
                wheelchair_accessible=random.choice([False, False, True]),
            )

            db.add(car)
            db.flush()  # Populates car.id via Postgres sequence

            photo1 = CarPhoto(
                car_id=car.id,  # Integer FK
                photo_url=f"https://placehold.co/800x600/222222/FFFFFF/png?text={car.make}+{car.model}+Exterior",
            )
            photo2 = CarPhoto(
                car_id=car.id,  # Integer FK
                photo_url=f"https://placehold.co/800x600/333333/FFFFFF/png?text={car.make}+{car.model}+Interior",
            )
            db.add_all([photo1, photo2])

            cars_created += 1

            if cars_created % 100 == 0:
                db.commit()
                print(f"  Assigned {cars_created}/{len(drivers)} vehicles...")

        db.commit()
        print(f" Successfully created {cars_created} vehicles and linked photo records for drivers!")

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding cars: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_driver_cars()