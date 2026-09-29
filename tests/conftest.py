import uuid
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app import models, utils

# -----------------------------------------------------------------------------
# Database Setup
# -----------------------------------------------------------------------------
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create database tables before tests run and clean up afterwards."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Provides a fresh transactional database session for each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with overridden database dependency."""
    def _get_test_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_test_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# -----------------------------------------------------------------------------
# Global Third-Party Mocks (SMS & Email)
# -----------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_third_party_services():
    """
    Globally mocks external Email and SMS OTP dispatches across all tests.
    Prevents live API calls, prevents charging credits, and works offline.
    """
    # Adjust target string paths if your functions are located elsewhere
    with patch("app.utils.send_otp", create=True) as mock_sms, patch(
        "app.utils.send_email", create=True
    ) as mock_email:

        mock_sms.return_value = {
            "status": "success",
            "msg": "Mocked OTP Sent Successfully",
            "verification_id": "mock-verification-id-12345",
        }

        mock_email.return_value = {
            "status": "success",
            "msg": "Mocked Confirmation Email Sent",
        }

        yield {"sms": mock_sms, "email": mock_email}


# -----------------------------------------------------------------------------
# Test User Fixture
# -----------------------------------------------------------------------------
@pytest.fixture
def test_user(db_session):
    """Creates a verified active user directly in the test database."""
    hashed_password = (
        utils.hash("password123")
        if hasattr(utils, "hash")
        else utils.pwd_context.hash("password123")
    )

    user = models.User(
        id=uuid.uuid4(),
        email="testuser@example.com",
        phone_number="08012345678",
        password=hashed_password,
        is_active=True,
        nin_verified=True,
        role="passenger",
    )

    # Automatically set verification flags if present on your model
    if hasattr(user, "is_verified"):
        user.is_verified = True
    if hasattr(user, "is_email_verified"):
        user.is_email_verified = True
    if hasattr(user, "is_phone_verified"):
        user.is_phone_verified = True

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user