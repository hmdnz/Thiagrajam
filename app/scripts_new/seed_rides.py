"""
Seed demo rides and ride occurrences across 100 days.

Required route coverage:
    Kano          -> every other city
    Abuja         -> every other city
    Kaduna        -> every other city
    Port Harcourt -> every other city
    Lagos         -> every other city

The four original major origins receive multiple trips on different dates.

Lagos receives 10 trips to every other supported city, spread across
the full 100-day period.

Additional random routes are also created so the demo database contains
more realistic variety.

This script is aligned with the current:
    - Ride
    - RideOccurrence
    - Stopover

models.

Important:
    Stopover uses `order_index`, not `order`.
"""

# -----------------------------------------------------------------------------
# Imports
# -----------------------------------------------------------------------------

import random
from datetime import date, timedelta, time

from app.database import SessionLocal
from app.models import User
from app.cars.models import Car
from app.rides.models import Ride, RideOccurrence, Stopover


# -----------------------------------------------------------------------------
# Random seed
# -----------------------------------------------------------------------------
# Using a fixed seed makes the demo data reproducible.
# Running the same clean seed again will produce predictable random choices.

random.seed(20261011)


# -----------------------------------------------------------------------------
# Supported cities
# -----------------------------------------------------------------------------
# Duplicate cities have been removed.
# Lagos only appears once even though it was mentioned multiple times
# in the original requirements.

CITIES = [
    "Kano",
    "Kaduna",
    "Dutse",
    "Abuja",
    "Lagos",
    "Sokoto",
    "Maiduguri",
    "Damaturu",
    "Benin",
    "Ibadan",
    "Enugu",
    "Owerri",
    "Port Harcourt",
    "Calabar",
    "Bauchi",
    "Gombe",
]


# -----------------------------------------------------------------------------
# Required major origins
# -----------------------------------------------------------------------------
# These origins must have trips to every other supported city.

REQUIRED_ORIGINS = [
    "Kano",
    "Abuja",
    "Kaduna",
    "Port Harcourt",
]


# -----------------------------------------------------------------------------
# Lagos route configuration
# -----------------------------------------------------------------------------
# Lagos is handled separately because you specifically requested:
#
#     Lagos -> every other location
#
# multiple times over a period of 100 days.
#
# There are 15 possible destinations from Lagos.
# Each destination receives 10 trips.
#
# 15 destinations x 10 trips = 150 Lagos-origin rides.

LAGOS_TRIPS_PER_DESTINATION = 10


# -----------------------------------------------------------------------------
# City metadata
# -----------------------------------------------------------------------------
# Coordinates and demo pickup/drop-off locations.

CITY_METADATA = {
    "Kano": {
        "lat": 12.0022,
        "lng": 8.5920,
        "pickup": [
            "Kano Central Motor Park",
            "Hotoro Roundabout",
            "Sabon Gari Park",
        ],
        "dropoff": [
            "Kano Central Business District",
            "Kofar Mata",
            "Farm Centre",
        ],
    },
    "Kaduna": {
        "lat": 10.5105,
        "lng": 7.4165,
        "pickup": [
            "Command Junction",
            "Kaduna North Motor Park",
            "Barnawa Junction",
        ],
        "dropoff": [
            "Kawo Park",
            "Kaduna Central",
            "Sabon Tasha",
        ],
    },
    "Dutse": {
        "lat": 11.7562,
        "lng": 9.3380,
        "pickup": [
            "Kiyawa Road Roundabout",
            "Dutse Motor Park",
            "Jigawa Secretariat Road",
        ],
        "dropoff": [
            "Dutse Central Motor Park",
            "GRA Dutse",
            "City Centre",
        ],
    },
    "Abuja": {
        "lat": 9.0765,
        "lng": 7.3986,
        "pickup": [
            "Utako Motor Park",
            "Berger Junction",
            "Jabi Park",
        ],
        "dropoff": [
            "Central Business District",
            "Area 1",
            "Garki",
        ],
    },
    "Lagos": {
        "lat": 6.5244,
        "lng": 3.3792,
        "pickup": [
            "Ojota Motor Park",
            "Berger Bus Stop",
            "Jibowu Park",
        ],
        "dropoff": [
            "Victoria Island",
            "Ikeja",
            "Ajah",
        ],
    },
    "Sokoto": {
        "lat": 13.0059,
        "lng": 5.2476,
        "pickup": [
            "Sokoto Central Motor Park",
            "Arkilla Park",
            "Gawon Nama",
        ],
        "dropoff": [
            "Sokoto Central Market",
            "Gawon Nama",
            "Sokoto City Centre",
        ],
    },
    "Maiduguri": {
        "lat": 11.8311,
        "lng": 13.1510,
        "pickup": [
            "Maiduguri Central Motor Park",
            "Bulumkutu Park",
            "Post Office Junction",
        ],
        "dropoff": [
            "Post Office Roundabout",
            "Monday Market",
            "Customs Area",
        ],
    },
    "Damaturu": {
        "lat": 11.7480,
        "lng": 11.9608,
        "pickup": [
            "Damaturu Motor Park",
            "Potiskum Road Junction",
            "Gashua Road",
        ],
        "dropoff": [
            "Damaturu Central",
            "Government House Road",
            "Main Market",
        ],
    },
    "Benin": {
        "lat": 6.3350,
        "lng": 5.6037,
        "pickup": [
            "Oluku Bypass",
            "Uselu Motor Park",
            "Ring Road",
        ],
        "dropoff": [
            "Ramat Park",
            "Stadium Road",
            "Benin City Centre",
        ],
    },
    "Ibadan": {
        "lat": 7.3775,
        "lng": 3.9470,
        "pickup": [
            "Iwo Road Motor Park",
            "Challenge Bus Stop",
            "Ojoo Park",
        ],
        "dropoff": [
            "Dugbe",
            "Bodija",
            "Mokola",
        ],
    },
    "Enugu": {
        "lat": 6.4584,
        "lng": 7.5464,
        "pickup": [
            "Holy Ghost Park",
            "New Haven Junction",
            "Abakpa Motor Park",
        ],
        "dropoff": [
            "Independence Layout",
            "Ogbete Market",
            "New Haven",
        ],
    },
    "Owerri": {
        "lat": 5.4763,
        "lng": 7.0259,
        "pickup": [
            "Owerri Main Motor Park",
            "Ikenegbu Junction",
            "Relief Market",
        ],
        "dropoff": [
            "Wetheral Road",
            "Douglas Road",
            "Owerri City Centre",
        ],
    },
    "Port Harcourt": {
        "lat": 4.8156,
        "lng": 7.0498,
        "pickup": [
            "Rumuokoro Motor Park",
            "Mile 3 Park",
            "Choba Junction",
        ],
        "dropoff": [
            "GRA Port Harcourt",
            "Trans Amadi",
            "Waterlines",
        ],
    },
    "Calabar": {
        "lat": 4.9757,
        "lng": 8.3417,
        "pickup": [
            "Watt Market Park",
            "8 Miles Junction",
            "Eta Agbor Roundabout",
        ],
        "dropoff": [
            "Calabar Road",
            "Marian Road",
            "Calabar City Centre",
        ],
    },
    "Bauchi": {
        "lat": 10.3158,
        "lng": 9.8442,
        "pickup": [
            "Bauchi Central Motor Park",
            "Yelwa Junction",
            "Wunti Market",
        ],
        "dropoff": [
            "Bauchi GRA",
            "Central Market",
            "Federal Secretariat",
        ],
    },
    "Gombe": {
        "lat": 10.2897,
        "lng": 11.1671,
        "pickup": [
            "Gombe Motor Park",
            "Pantami Stadium Junction",
            "Tashan Dukku",
        ],
        "dropoff": [
            "Gombe Main Market",
            "GRA Gombe",
            "Pantami",
        ],
    },
}


# -----------------------------------------------------------------------------
# Possible demo stopovers
# -----------------------------------------------------------------------------

STOPOVERS = [
    "Lokoja Junction",
    "Zaria Junction",
    "Keffi Bypass",
    "Ore Bypass",
    "Akure Junction",
    "Okene Junction",
    "Onitsha Junction",
    "Kano Road Junction",
]


# -----------------------------------------------------------------------------
# Fare calculation
# -----------------------------------------------------------------------------

def route_price(origin: str, destination: str) -> float:
    """
    Estimate a consistent demo fare from the city coordinates.

    This is only for seed/demo data.

    It is NOT a production distance or pricing engine.
    """

    origin_data = CITY_METADATA[origin]
    destination_data = CITY_METADATA[destination]

    # Calculate a simple coordinate-distance score.
    distance_score = (
        (
            (origin_data["lat"] - destination_data["lat"]) ** 2
            + (origin_data["lng"] - destination_data["lng"]) ** 2
        )
        ** 0.5
    )

    # Base fare plus distance component.
    price = 4500 + (distance_score * 2600)

    # Round the demo fare to the nearest ₦500.
    return float(max(5000, round(price / 500) * 500))


# -----------------------------------------------------------------------------
# Create one ride
# -----------------------------------------------------------------------------

def create_ride(
    db,
    driver: User,
    car: Car,
    origin: str,
    destination: str,
    travel_date: date,
):
    """
    Create:

        1. Ride
        2. RideOccurrence
        3. Optional Stopover
    """

    origin_meta = CITY_METADATA[origin]
    destination_meta = CITY_METADATA[destination]

    # Get vehicle capacity.
    capacity = max(2, car.capacity or 4)

    # Reserve one seat for the driver.
    max_passengers = min(
        capacity - 1,
        random.choice([2, 3, 3]),
    )

    # Create the main ride.
    ride = Ride(
        driver_id=driver.id,
        car_id=car.id,

        # Origin information.
        origin_city=origin,
        pickup_location=random.choice(origin_meta["pickup"]),
        pickup_lat=origin_meta["lat"],
        pickup_lng=origin_meta["lng"],

        # Destination information.
        destination_city=destination,
        dropoff_location=random.choice(destination_meta["dropoff"]),
        dropoff_lat=destination_meta["lat"],
        dropoff_lng=destination_meta["lng"],

        # Random departure time between 5:00 AM and 4:45 PM.
        pickup_time=time(
            random.randint(5, 16),
            random.choice([0, 15, 30, 45]),
        ),

        # Demo fare.
        price_per_seat=route_price(
            origin,
            destination,
        ),

        # Passenger capacity.
        max_passengers=max_passengers,
        max_back_seat_passengers=max(
            1,
            max_passengers - 1,
        ),

        # Booking configuration.
        instant_booking=random.choice([True, False]),

        # These are individual rides, not recurring rides.
        is_recurring=False,
        recurrence_type=None,
        custom_days=None,

        # The ride starts on this travel date.
        start_date=travel_date,
        end_date=None,

        # Ride is available.
        is_active=True,
    )

    db.add(ride)

    # Flush so SQLAlchemy generates ride.id before creating
    # the RideOccurrence and Stopover records.
    db.flush()

    # -------------------------------------------------------------------------
    # Create occurrence
    # -------------------------------------------------------------------------

    db.add(
        RideOccurrence(
            ride_id=ride.id,
            date=travel_date,
            seats_remaining=max_passengers,
            is_cancelled=False,
        )
    )

    # -------------------------------------------------------------------------
    # Optional stopover
    # -------------------------------------------------------------------------
    # Approximately 45% of demo rides receive a stopover.

    if random.random() < 0.45:
        db.add(
            Stopover(
                ride_id=ride.id,
                city_name=random.choice(STOPOVERS),
                address="Main Road Junction",

                # IMPORTANT:
                # The current Stopover model uses order_index.
                order_index=1,

                price_from_origin=round(
                    route_price(origin, destination) * 0.5,
                    2,
                ),
            )
        )

    return ride


# -----------------------------------------------------------------------------
# Seed rides
# -----------------------------------------------------------------------------

def seed_rides() -> None:
    """
    Create the complete 100-day demo ride schedule.

    Required schedule:

        1. Kano -> every other city
        2. Abuja -> every other city
        3. Kaduna -> every other city
        4. Port Harcourt -> every other city
        5. Lagos -> every other city, 10 trips per destination

    Additional random rides are then added across the 100-day period.
    """

    db = SessionLocal()

    try:

        # ---------------------------------------------------------------------
        # Find demo drivers
        # ---------------------------------------------------------------------
        # NOTE:
        # This matches the CURRENT seed_users.py format used by the original
        # seed script.
        #
        # If you have already changed seed_users.py to:
        #
        #     d-obinna@rideapp.ng
        #
        # then this query must also be updated.
        #
        # The updated version below supports BOTH:
        #
        #     demo.driver.xxx@rideapp.ng
        #
        # and
        #
        #     d-...@rideapp.ng
        # ---------------------------------------------------------------------

        drivers = (
            db.query(User)
            .filter(
                User.is_driver.is_(True),
                User.email.ilike("%@rideapp.ng"),
            )
            .order_by(User.email)
            .all()
        )

        if not drivers:
            print(
                "No demo drivers found. "
                "Run seed_users.py first."
            )
            return

        # ---------------------------------------------------------------------
        # Map each driver to their car
        # ---------------------------------------------------------------------

        driver_cars = {}

        for driver in drivers:
            car = (
                db.query(Car)
                .filter(Car.driver_id == driver.id)
                .first()
            )

            if car:
                driver_cars[driver.id] = car

        if not driver_cars:
            print(
                "No demo driver cars found. "
                "Run seed_cars.py first."
            )
            return

        # ---------------------------------------------------------------------
        # Date configuration
        # ---------------------------------------------------------------------
        #
        # Tomorrow is Day 1.
        #
        # We generate rides over a 100-day calendar window.
        #
        # Day offsets:
        #
        #     0 = tomorrow
        #     99 = 100th day
        #
        # This gives exactly 100 calendar days.
        # ---------------------------------------------------------------------

        first_day = date.today() + timedelta(days=1)

        # Original major-origin schedule.
        #
        # Each route gets 4 different dates:
        #
        #     Day 1
        #     Day 30
        #     Day 55
        #     Day 80
        #
        # This preserves the original route matrix.
        major_origin_offsets = [
            5,
            30,
            55,
            80,
        ]

        # Lagos schedule.
        #
        # 10 different dates spread across the 100-day period.
        #
        # These are intentionally spread rather than grouped together.
        lagos_offsets = [
            2,
            12,
            22,
            32,
            42,
            52,
            62,
            72,
            82,
            92,
        ]

        # Counters for reporting.
        rides_created = 0

        required_route_count = 0
        lagos_route_count = 0

        driver_index = 0

        # ---------------------------------------------------------------------
        # PART 1
        # Required routes for Kano, Abuja, Kaduna and Port Harcourt.
        # ---------------------------------------------------------------------
        #
        # 4 origins
        # x 15 destinations
        # x 4 dates
        #
        # = 240 rides
        # ---------------------------------------------------------------------

        print("")
        print("Creating major-origin routes...")

        for origin in REQUIRED_ORIGINS:

            for destination in CITIES:

                # Never create a city -> itself route.
                if destination == origin:
                    continue

                required_route_count += 1

                for offset in major_origin_offsets:

                    travel_date = (
                        first_day
                        + timedelta(days=offset)
                    )

                    # Rotate drivers so the trips are distributed
                    # across the available drivers.
                    driver = drivers[
                        driver_index % len(drivers)
                    ]

                    driver_index += 1

                    car = driver_cars.get(driver.id)

                    # Skip a driver if no car is attached.
                    if not car:
                        continue

                    create_ride(
                        db=db,
                        driver=driver,
                        car=car,
                        origin=origin,
                        destination=destination,
                        travel_date=travel_date,
                    )

                    rides_created += 1

        print(
            f"Major-origin routes created: "
            f"{required_route_count}"
        )

        # ---------------------------------------------------------------------
        # PART 2
        # Lagos -> every other city.
        # ---------------------------------------------------------------------
        #
        # Lagos has 15 possible destinations.
        #
        # Each destination receives 10 trips.
        #
        # 15 destinations x 10 trips
        #
        # = 150 Lagos-origin rides.
        # ---------------------------------------------------------------------

        print("")
        print("Creating Lagos routes...")

        for destination in CITIES:

            # Lagos cannot travel to Lagos.
            if destination == "Lagos":
                continue

            lagos_route_count += 1

            for offset in lagos_offsets:

                travel_date = (
                    first_day
                    + timedelta(days=offset)
                )

                # Rotate through drivers.
                driver = drivers[
                    driver_index % len(drivers)
                ]

                driver_index += 1

                car = driver_cars.get(driver.id)

                if not car:
                    continue

                create_ride(
                    db=db,
                    driver=driver,
                    car=car,
                    origin="Lagos",
                    destination=destination,
                    travel_date=travel_date,
                )

                rides_created += 1

        print(
            f"Lagos route pairs created: "
            f"{lagos_route_count}"
        )

        print(
            f"Lagos trips created: "
            f"{lagos_route_count * len(lagos_offsets)}"
        )

        # ---------------------------------------------------------------------
        # PART 3
        # Additional random routes.
        # ---------------------------------------------------------------------
        #
        # These make the demo database more realistic.
        #
        # We create two random rides every two days.
        #
        # 50 days x 2 rides = approximately 100 additional rides.
        # ---------------------------------------------------------------------

        print("")
        print("Creating additional random routes...")

        random_rides_created = 0

        for day_offset in range(0, 100, 2):

            travel_date = (
                first_day
                + timedelta(days=day_offset)
            )

            for _ in range(2):

                # Pick two different cities.
                origin, destination = random.sample(
                    CITIES,
                    2,
                )

                driver = drivers[
                    driver_index % len(drivers)
                ]

                driver_index += 1

                car = driver_cars.get(driver.id)

                if not car:
                    continue

                create_ride(
                    db=db,
                    driver=driver,
                    car=car,
                    origin=origin,
                    destination=destination,
                    travel_date=travel_date,
                )

                rides_created += 1
                random_rides_created += 1

        # ---------------------------------------------------------------------
        # Commit everything
        # ---------------------------------------------------------------------

        db.commit()

        # ---------------------------------------------------------------------
        # Final report
        # ---------------------------------------------------------------------

        print("")
        print("=" * 60)
        print("DEMO RIDE SEED COMPLETED")
        print("=" * 60)

        print(
            f"Major-origin route pairs: "
            f"{required_route_count}"
        )

        print(
            f"Major-origin rides: "
            f"{required_route_count * len(major_origin_offsets)}"
        )

        print(
            f"Lagos route pairs: "
            f"{lagos_route_count}"
        )

        print(
            f"Lagos rides: "
            f"{lagos_route_count * len(lagos_offsets)}"
        )

        print(
            f"Additional random rides: "
            f"{random_rides_created}"
        )

        print(
            f"TOTAL RIDES CREATED: "
            f"{rides_created}"
        )

        print(
            f"Schedule window: "
            f"{first_day} -> "
            f"{first_day + timedelta(days=99)}"
        )

        print("=" * 60)

    except Exception:

        # Roll back everything if any ride fails.
        db.rollback()

        raise

    finally:

        # Always close the database connection.
        db.close()


# -----------------------------------------------------------------------------
# Run directly
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    seed_rides()