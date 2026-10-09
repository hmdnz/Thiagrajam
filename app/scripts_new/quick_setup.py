"""
Run the complete demo-data seed in the correct dependency order.

Order:
    1. users       -> 20 drivers + 100 passengers
    2. cars        -> one car per demo driver
    3. rides       -> 100-day ride schedule
    4. bookings    -> passenger bookings against the rides
"""

# Add the project root to Python's import path.
# This allows imports such as "from app.database import ..."
# to work when this script is executed directly.
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from seed_users import seed_users
from seed_cars import seed_driver_cars
from seed_rides import seed_rides
from seed_bookings import seed_bookings


if __name__ == "__main__":
    seed_users()
    seed_driver_cars()
    seed_rides()
    seed_bookings()
    print("\nDemo data seeding completed successfully.")
