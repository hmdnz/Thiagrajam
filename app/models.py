"""
app/models.py
"""

import enum
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    TIMESTAMP,
    Date,
    DateTime,
    Enum,
    Float,
    Text,
    text,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from .database import Base

# Import feature models to prevent duplicate metadata registration
from app.cars.models import Car
from app.bookings.models import Booking, BookingStatusEnum
from app.rides.models import Ride, RideOccurrence, Stopover


# ---------------------------------------------------------------
# Enums
# ---------------------------------------------------------------

class UserRoleEnum(enum.Enum):
    passenger = "passenger"
    driver = "driver"


class GenderEnum(enum.Enum):
    male = "male"
    female = "female"


class BloodGroupEnum(enum.Enum):
    a_positive = "A+"
    a_negative = "A-"
    b_positive = "B+"
    b_negative = "B-"
    ab_positive = "AB+"
    ab_negative = "AB-"
    o_positive = "O+"
    o_negative = "O-"
    unknown = "unknown"


class VerificationStatusEnum(enum.Enum):
    unverified = "unverified"
    pending = "pending"
    verified = "verified"
    failed = "failed"


class ChattinessEnum(enum.Enum):
    very_talkative = "Very talkative!"
    warm_up = "I chat once I warm up"
    quiet = "Quiet rider"


class MusicEnum(enum.Enum):
    always_playing = "Always playing tunes!"
    depends_on_mood = "Music depends on the mood"
    no_music = "Prefer no music"


class SmokingEnum(enum.Enum):
    allowed = "Smoking allowed in the vehicle"
    outside_breaks = "Smoke breaks outside the car only"
    no_smoking = "Strictly smoke-free ride"


class PetsEnum(enum.Enum):
    pet_friendly = "Pet-friendly ride!"
    case_by_case = "Open to pets depending on type/size"
    no_pets = "No pets allowed"


# ---------------------------------------------------------------
# User Model
# ---------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=True, index=True)
    phone_number = Column(String, unique=True, nullable=True, index=True)
    password = Column(String, nullable=False)

    nin_verified = Column(Boolean, server_default="false", nullable=False)
    is_active = Column(Boolean, server_default="true", nullable=False)
    is_admin = Column(Boolean, server_default="false", nullable=False)
    otp_verification_id = Column(String, nullable=True)

    full_name = Column(String, nullable=True)
    address = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(Enum(GenderEnum), nullable=True)

    next_of_kin_name = Column(String, nullable=True)
    next_of_kin_relationship = Column(String, nullable=True)
    emergency_contact = Column(String, nullable=True)

    blood_group = Column(Enum(BloodGroupEnum), nullable=True)
    health_conditions = Column(Text, nullable=True)

    nin = Column(String, unique=True, nullable=True)
    photo_url = Column(String, nullable=True)
    nin_verification_status = Column(
        Enum(VerificationStatusEnum),
        default=VerificationStatusEnum.unverified,
        server_default=VerificationStatusEnum.unverified.value,
        nullable=False,
    )
    nin_verified_at = Column(TIMESTAMP(timezone=True), nullable=True)
    nin_match_score = Column(Float, nullable=True)
    nin_verification_notes = Column(String, nullable=True)

    role = Column(Enum(UserRoleEnum), default=UserRoleEnum.passenger, nullable=False)
    profile_complete = Column(Boolean, server_default="false", nullable=False)

    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    # Relationships
    posts = relationship("Post", back_populates="owner")
    driver_profile = relationship(
        "DriverProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    cars = relationship(Car, back_populates="owner", cascade="all, delete-orphan")
    rides = relationship("Ride", back_populates="driver", cascade="all, delete-orphan")
    bookings = relationship(Booking, back_populates="passenger", cascade="all, delete-orphan")

    # -----------------------------------------------------------
    # Profile Completion Helper Method
    # -----------------------------------------------------------
    def update_profile_complete(self) -> bool:
        """
        Evaluates whether required passenger profile fields are populated,
        updates self.profile_complete accordingly, and returns the result.
        """
        required_fields = [
            self.full_name,
            self.address,
            self.phone_number,
            self.date_of_birth,
            self.gender,
            self.next_of_kin_name,
            self.emergency_contact,
            self.blood_group,
            self.nin,
            self.photo_url,
        ]

        self.profile_complete = all(
            field is not None and str(field).strip() != ""
            for field in required_fields
        )

        return self.profile_complete

    # -----------------------------------------------------------
    # Computed Properties for Response Schemas
    # -----------------------------------------------------------
    @property
    def is_passenger(self) -> bool:
        return self.role == UserRoleEnum.passenger

    @property
    def is_driver(self) -> bool:
        return self.role == UserRoleEnum.driver

    @property
    def has_driver_application(self) -> bool:
        return self.driver_profile is not None

    @property
    def can_book_rides(self) -> bool:
        """
        A passenger can book rides if account is active and passenger profile is complete.
        """
        return self.is_active and self.profile_complete

    @property
    def can_offer_rides(self) -> bool:
        """
        A driver can offer rides if account is active, passenger profile is complete,
        driver profile exists, and driving licence status is verified.
        """
        if not (self.is_active and self.profile_complete and self.driver_profile):
            return False

        return (
            self.driver_profile.license_verification_status
            == VerificationStatusEnum.verified
        )


# ---------------------------------------------------------------
# Driver Profile
# ---------------------------------------------------------------

class DriverProfile(Base):
    __tablename__ = "driver_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    license_number = Column(String, unique=True, nullable=True)
    license_photo_url = Column(String, nullable=True)
    license_expiry_date = Column(Date, nullable=True)
    about_me = Column(Text, nullable=True)

    chattiness = Column(Enum(ChattinessEnum), nullable=True)
    music = Column(Enum(MusicEnum), nullable=True)
    smoking = Column(Enum(SmokingEnum), nullable=True)
    pets = Column(Enum(PetsEnum), nullable=True)

    license_verification_status = Column(
        Enum(VerificationStatusEnum),
        default=VerificationStatusEnum.unverified,
        server_default=VerificationStatusEnum.unverified.value,
        nullable=False,
    )
    license_verification_notes = Column(String, nullable=True)

    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    user = relationship("User", back_populates="driver_profile")

    # -----------------------------------------------------------
    # Driver Profile Completion Helper Method
    # -----------------------------------------------------------
    def is_complete(self) -> bool:
        """
        Checks if required driver profile fields (licence number, 
        licence photo, and expiry date) are populated.
        """
        required_fields = [
            self.license_number,
            self.license_photo_url,
            self.license_expiry_date,
        ]

        return all(
            field is not None and str(field).strip() != ""
            for field in required_fields
        )


# ---------------------------------------------------------------
# Misc Models
# ---------------------------------------------------------------

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, nullable=False)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    published = Column(Boolean, server_default="TRUE", nullable=False)
    rating = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    owner_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    owner = relationship("User", back_populates="posts")


class PhoneVerification(Base):
    __tablename__ = "phone_verifications"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, nullable=False, index=True)
    otp_hash = Column(String, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())