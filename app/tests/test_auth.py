import pytest


def test_login_success_with_email(client, test_user):
    """Test successful login using email."""
    response = client.post(
        "/auth/login",
        data={"username": "testuser@example.com", "password": "password123"}
    )
    assert response.status_code == 200
    res_data = response.json()
    assert "access_token" in res_data
    assert res_data["token_type"] == "bearer"
    assert res_data["user_id"] == str(test_user.id)


def test_login_success_with_phone(client, test_user):
    """Test successful login using formatted Nigerian phone number."""
    response = client.post(
        "/auth/login",
        data={"username": "08012345678", "password": "password123"}
    )
    assert response.status_code == 200
    res_data = response.json()
    assert "access_token" in res_data


def test_login_invalid_password(client, test_user):
    """Test 401 when passing an incorrect password."""
    response = client.post(
        "/auth/login",
        data={"username": "testuser@example.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_user_not_found(client):
    """Test 401 when user does not exist in DB."""
    response = client.post(
        "/auth/login",
        data={"username": "nonexistent@example.com", "password": "password123"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_deactivated_user(client, db_session, test_user):
    """Test 403 when account is inactive."""
    test_user.is_active = False
    db_session.commit()

    response = client.post(
        "/auth/login",
        data={"username": "testuser@example.com", "password": "password123"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Your account is deactivated."