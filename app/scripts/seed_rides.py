import random
from datetime import date, datetime, timedelta, time
from app.database import SessionLocal
from app.rides.models import Ride, RideOccurrence, Stopover
from app.cars.models import Car
from app.models import User

# List of target cities in Nigeria
CITIES = [
    "Abuja", "Kaduna", "Dutse", "Maiduguri", "Nassarawa", "Makurdi",
    "Yola", "Sokoto", "Gusau", "Lagos", "Katsina", "Jos", "Benin", "Calabar"
]

# Inter-city route coordinates & locations
CITY_METADATA = {
    "Abuja": {"lat": 9.0765, "lng": 7.3986, "pickup": "Berger Junction / Utako Motor Park", "dropoff": "Central Business District"},
    "Kaduna": {"lat": 10.5105, "lng": 7.4165, "pickup": "Command Junction", "dropoff": "Kawo Park"},
    "Dutse": {"lat": 11.7024, "lng": 9.3503, "pickup": "Kiyawa Road Roundabout", "dropoff": "Central Motor Park"},
    "Maiduguri": {"lat": 11.8311, "lng": 13.1510, "pickup": "Kano Park, Bulumkutu", "dropoff": "Post Office Roundabout"},
    "Nassarawa": {"lat": 8.5383, "lng": 7.7088, "pickup": "Lafia Junction", "dropoff": "Town Center"},
    "Makurdi": {"lat": 7.7322, "lng": 8.5391, "pickup": "Wurukum Roundabout", "dropoff": "High Level Motor Park"},
    "Yola": {"lat": 9.2035, "lng": 12.4954, "pickup": "Jambutu Motor Park", "dropoff": "Jimeta Shopping Complex"},
    "Sokoto": {"lat": 13.0059, "lng": 5.2476, "pickup": "Central Market Bus Stop", "dropoff": "Sokoto Roundabout"},
    "Gusau": {"lat": 12.1628, "lng": 6.6614, "pickup": "Canteen Daji Area", "dropoff": "Gusau Central Park"},
    "Lagos": {"lat": 6.5244, "lng": 3.3792, "pickup": "Berger Bus Stop, Ikeja", "dropoff": "Ojota / Ajah Jubilee Bridge"},
    "Katsina": {"lat": 12.9887, "lng": 7.6009, "pickup": "Kofar Kaura Roundabout", "dropoff": "Central Park"},
    "Jos": {"lat": 9.8965, "lng": 8.8583, "pickup": "British-America Junction", "dropoff": "Terminus Main Market"},
    "Benin": {"lat": 6.3350, "lng": 5.6037, "pickup": "Oluku Bypass / Uselu", "dropoff": "Ramat Park"},
    "Calabar": {"lat": 4.9757, "lng": 8.3417, "pickup": "Eta Agbor Roundabout", "dropoff": "Watt Market Area"},
}

COMMON_STOPOVERS = [
    "Lokoja Expressway Junction", "Ore Bypass", "Akure Junction",
    "Zaria Toll Gate", "Kano Road Junction", "Keffi Bypass"
]


def calculate_base_price(origin: str, dest: str) -> float:
    """Calculates a realistic price based on rough distance between coordinates."""
    o_data = CITY_METADATA[origin]
    d_data = CITY_METADATA[dest]
    
    dist = ((o_data["lat"] - d_data["lat"])**2 + (o_data["lng"] - d_data["lng"])**2) ** 0.5
    estimated_price = 3000 + (dist * 2200)
    rounded_price = round(estimated_price / 500) * 500
    return float(max(4000.0, rounded_price))


def get_car_owner_field():
    """Dynamically checks if Car uses user_id, owner_id, or driver_id as foreign key."""
    if hasattr(Car, "user_id"):
        return Car.user_id
    elif hasattr(Car, "owner_id"):
        return Car.owner_id
    elif hasattr(Car, "driver_id"):
        return Car.driver_id
    else:
        raise AttributeError("Car model has no recognized user foreign key.")


def seed_rides():
    db = SessionLocal()
    try:
        car_user_fk = get_car_owner_field()

        # Fetch active drivers
        drivers = db.query(User).filter(
            User.is_driver == True, 
            User.is_active == True
        ).all()

        if not drivers:
            print("❌ No active drivers found in the database. Run user seeder first.")
            return

        # Map drivers to their cars
        driver_cars_map = {}
        for driver in drivers:
            cars = db.query(Car).filter(car_user_fk == driver.id).all()
            if cars:
                driver_cars_map[driver.id] = cars

        if not driver_cars_map:
            print("❌ No cars found associated with active drivers. Run car seeder first.")
            return

        driver_ids = list(driver_cars_map.keys())
        print(f"Found {len(driver_ids)} drivers with registered vehicles.")

        today = date.today()
        start_date = today + timedelta(days=1)
        total_days = 90

        rides_created = 0
        occurrences_created = 0

        # Generate rides across 90 days
        for day_offset in range(total_days):
            current_date = start_date + timedelta(days=day_offset)
            weekday = current_date.weekday()

            num_rides_today = random.randint(12, 20) if weekday in [0, 4, 5, 6] else random.randint(4, 9)

            for _ in range(num_rides_today):
                driver_id = random.choice(driver_ids)
                car = random.choice(driver_cars_map[driver_id])

                origin_city, destination_city = random.sample(CITIES, 2)
                origin_meta = CITY_METADATA[origin_city]
                dest_meta = CITY_METADATA[destination_city]
                price = calculate_base_price(origin_city, destination_city)

                car_seats = getattr(car, "seats", None) or getattr(car, "capacity", None) or getattr(car, "seats_available", 4)
                max_passengers = min(car_seats - 1, random.choice([3, 4, 6]))
                max_passengers = max(1, max_passengers)

                if random.random() < 0.7:
                    pickup_time = time(hour=random.randint(6, 10), minute=random.choice([0, 15, 30, 45]))
                else:
                    pickup_time = time(hour=random.randint(13, 17), minute=random.choice([0, 15, 30, 45]))

                is_recurring = random.choice([True, False])

                ride = Ride(
                    driver_id=driver_id,
                    car_id=car.id,
                    origin_city=origin_city,
                    destination_city=destination_city,
                    pickup_location=origin_meta["pickup"],
                    dropoff_location=dest_meta["dropoff"],
                    pickup_time=pickup_time,
                    start_date=current_date,
                    end_date=current_date + timedelta(days=30) if is_recurring else None,
                    is_recurring=is_recurring,
                    max_passengers=max_passengers,
                    price_per_seat=price,
                    is_active=True
                )
                db.add(ride)
                db.flush()

                occurrence = RideOccurrence(
                    ride_id=ride.id,
                    date=current_date,
                    seats_remaining=random.randint(1, max_passengers),
                    is_cancelled=False
                )
                db.add(occurrence)
                occurrences_created += 1

                if random.random() < 0.4:
                    stopover_name = random.choice(COMMON_STOPOVERS)
                    stopover = Stopover(
                        ride_id=ride.id,
                        city_name=stopover_name,
                        address=f"{stopover_name} Main Station",
                        order=1,
                        price_from_origin=round(price * 0.5, 2)
                    )
                    db.add(stopover)

                rides_created += 1

        db.commit()
        print(f"Successfully created {rides_created} rides and {occurrences_created} occurrences across 90 days!")

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding rides: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed_rides()