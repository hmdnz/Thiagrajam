"""
scripts/quick_setup.py

Sets up a driver + car + ride + booking, and flips the passenger's
verification flags so they can book. Prints the tokens and IDs
you need for the payment test.

Run: python -m scripts.quick_setup
"""

import time
import requests


BASE = "http://127.0.0.1:8000"
PW = "test1234"


def hr(title):
    print(f"\n{'=' * 55}\n{title}\n{'=' * 55}")


def post(path, **kw):
    r = requests.post(f"{BASE}{path}", **kw)
    if r.status_code >= 400:
        print(f"  ! {path} -> {r.status_code}: {r.text[:300]}")
    return r


def main():
    ts = int(time.time())
    passenger_email = f"passenger{ts}@test.com"
    driver_email = f"driver{ts}@test.com"

    # ---------------- Passenger ----------------
    hr("Register passenger")
    post("/auth/register", json={
        "email": passenger_email,
        "password": PW,
        "full_name": "Test Passenger",
        "phone": "08011111111",
    })

    r = post("/auth/login", data={
        "username": passenger_email,
        "password": PW,
    })
    passenger_token = r.json()["access_token"]
    print(f"  passenger_email: {passenger_email}")
    print(f"  passenger_token: {passenger_token[:40]}...")

    # ---------------- Driver ----------------
    hr("Register driver")
    post("/auth/register", json={
        "email": driver_email,
        "password": PW,
        "full_name": "Test Driver",
        "phone": "08022222222",
    })

    r = post("/auth/login", data={
        "username": driver_email,
        "password": PW,
    })
    driver_token = r.json()["access_token"]
    print(f"  driver_email: {driver_email}")
    print(f"  driver_token: {driver_token[:40]}...")

    # ---------------- Flip verification flags directly in DB ----------------
    hr("Flip verification flags (needed so passenger can book, driver can post)")
    from app.database import SessionLocal
    from app import models

    db = SessionLocal()
    try:
        db.query(models.User).filter(
            models.User.email == passenger_email
        ).update({
            "profile_completed": True,
            "nin_verified": True,
        })
        db.query(models.User).filter(
            models.User.email == driver_email
        ).update({
            "profile_completed": True,
            "nin_verified": True,
            "licence_verified": True,
            "can_offer_rides": True,
        })
        db.commit()
        print("  flags updated")
    finally:
        db.close()

    # ---------------- Driver: create car ----------------
    hr("Create car (driver)")
    r = post(
        "/cars/",
        headers={"Authorization": f"Bearer {driver_token}"},
        json={
            "make": "Toyota",
            "model": "Camry",
            "year": 2020,
            "color": "Silver",
            "plate_number": f"TEST{ts % 100000}",
            "seats": 4,
            "is_tinted": False,
            "has_wifi": True,
            "has_air_conditioning": True,
            "has_power_outlets": False,
            "smoking_allowed": False,
            "pets_allowed": False,
            "wheelchair_accessible": False,
        },
    )
    print(f"  car create status: {r.status_code}")
    car_id = r.json().get("id")
    print(f"  car_id: {car_id}")

    # ---------------- Driver: create ride ----------------
    hr("Create ride (driver)")
    from datetime import date, timedelta
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    r = post(
        "/rides/",
        headers={"Authorization": f"Bearer {driver_token}"},
        json={
            "car_id": car_id,
            "origin_city": "Kano",
            "destination_city": "Abuja",
            "pickup_location": "Kano Central Park",
            "dropoff_location": "Abuja Wuse Market",
            "dates": [tomorrow],
            "pickup_time": "08:00:00",
            "max_passengers": 4,
            "instant_booking": True,
            "price_per_seat": 5000,
        },
    )
    print(f"  ride create status: {r.status_code}")
    ride_id = r.json().get("id")
    print(f"  ride_id: {ride_id}")
    print(f"  travel_date: {tomorrow}")

    # ---------------- Passenger: create booking ----------------
    hr("Create booking (passenger)")
    r = post(
        "/bookings/",
        headers={"Authorization": f"Bearer {passenger_token}"},
        json={
            "ride_id": ride_id,
            "ride_date": tomorrow,
            "seats_booked": 1,
        },
    )
    print(f"  booking create status: {r.status_code}")
    print(f"  response: {r.text[:300]}")
    booking_id = r.json().get("id")
    print(f"  booking_id: {booking_id}")

    # ---------------- Summary ----------------
    hr("COPY THESE FOR THE PAYMENT TEST")
    print(f"PASSENGER_TOKEN={passenger_token}")
    print(f"DRIVER_TOKEN={driver_token}")
    print(f"BOOKING_ID={booking_id}")
    print()


if __name__ == "__main__":
    main()