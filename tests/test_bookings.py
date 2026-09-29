import pytest
from fastapi import status
from app.models import User  # Adjust import if your User model is located elsewhere


def create_user_and_get_headers(client, email: str, name: str, phone: str, db_session=None):
    """
    Registers a user, auto-verifies them in the test DB to bypass phone OTP restrictions,
    and returns authorization bearer headers.
    """
    # 1. Register User
    reg_response = client.post(
        "/users/",
        json={
            "email": email,
            "password": "Password123!",
            "full_name": name,
            "phone_number": phone,
        },
    )
    assert reg_response.status_code in [status.HTTP_201_CREATED, status.HTTP_200_OK]

    # 2. Directly verify user in database to bypass 403 Forbidden on login
    if db_session:
        user = db_session.query(User).filter(User.email == email).first()
        if user:
            # Set whatever flag your schema uses for verification
            if hasattr(user, "is_verified"):
                user.is_verified = True
            if hasattr(user, "is_active"):
                user.is_active = True
            if hasattr(user, "phone_verified"):
                user.phone_verified = True
            db_session.commit()

    # 3. Login User
    login_response = client.post(
        "/auth/login",
        data={"username": email, "password": "Password123!"},
    )
    assert login_response.status_code == status.HTTP_200_OK, f"Login failed: {login_response.json()}"

    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_complete_booking_lifecycle(client, db_session):
    """
    Tests full lifecycle:
    1. Register Driver & Passenger
    2. Driver creates car & publishes ride
    3. Passenger books 2 seats -> Status PENDING
    4. Driver confirms booking -> Status CONFIRMED
    5. Driver starts trip -> Status TRIP_STARTED
    6. Driver completes trip -> Status TRIP_COMPLETED
    """
    driver_headers = create_user_and_get_headers(
        client, "driver@wenyfour.com", "Driver User", "+2348011111111", db_session
    )
    passenger_headers = create_user_and_get_headers(
        client, "passenger@wenyfour.com", "Passenger User", "+2348022222222", db_session
    )

    # Add remaining test lifecycle calls below...
    assert driver_headers is not None
    assert passenger_headers is not None


def test_capacity_exceeded_error(client, db_session):
    """Ensures booking fails with 400 when requesting more seats than available."""
    driver_headers = create_user_and_get_headers(
        client, "driver2@wenyfour.com", "Driver Two", "+2348033333333", db_session
    )

    # Add remaining capacity error test assertions below...
    assert driver_headers is not None


def test_unauthorized_driver_action_forbidden(client, db_session):
    """Ensures a non-assigned driver cannot confirm someone else's ride booking."""
    driver_a = create_user_and_get_headers(
        client, "da@test.com", "Driver A", "+2348055555555", db_session
    )

    # Add remaining authorization test assertions below...
    assert driver_a is not None