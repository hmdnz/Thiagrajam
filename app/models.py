"""
app/models.py

Core shared SQLAlchemy ORM models and Enums for User, DriverProfile,
Post, Ride, Booking, Payment, and Review entities.
"""
from app.cars.models import Car
import enum
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UUID,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base

# ===============================================================
# ENUMS
# ===============================================================

class UserRoleEnum(str, enum.Enum):
    passenger = "passenger"
    driver = "driver"
    admin = "admin"


class VerificationStatusEnum(str, enum.Enum):
    unverified = "unverified"
    pending = "pending"
    verified = "verified"
    rejected = "rejected"


class GenderEnum(str, enum.Enum):
    male = "male"
    female = "female"
    other = "other"


class BloodGroupEnum(str, enum.Enum):
    a_positive = "A+"
    a_negative = "A-"
    b_positive = "B+"
    b_negative = "B-"
    ab_positive = "AB+"
    ab_negative = "AB-"
    o_positive = "O+"
    o_negative = "O-"


class ChattinessEnum(str, enum.Enum):
    very_talkative = "Very talkative!"
    warm_up = "I chat once I warm up"
    quiet = "Quiet rider"
    chatty = "chatty"  # <--- Add this missing value


class MusicEnum(str, enum.Enum):
    always_playing = "Always playing tunes!"
    depends_on_mood = "Music depends on the mood"
    no_music = "Prefer no music"
    


class SmokingEnum(str, enum.Enum):
    allowed = "Smoking allowed in the vehicle"
    outside_breaks = "Smoke breaks outside the car only"
    no_smoking = "Strictly smoke-free ride"


class PetsEnum(str, enum.Enum):
    pet_friendly = "Pet-friendly ride!"
    case_by_case = "Open to pets depending on type/size"
    no_pets = "No pets allowed"


class RideStatusEnum(str, enum.Enum):
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class BookingStatusEnum(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"


class PaymentStatusEnum(str, enum.Enum):
    pending = "pending"
    successful = "successful"
    failed = "failed"
    refunded = "refunded"


# ===============================================================
# MODELS
# ===============================================================

class Post(Base):
    __tablename__ = "posts"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    published = Column(Boolean, default=True, nullable=False)
    rating = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    full_name = Column(String, nullable=True)
    email = Column(String, unique=True, nullable=True, index=True)
    phone_number = Column(String, unique=True, nullable=True, index=True)
    password = Column(String, nullable=False)
    role = Column(SQLEnum(UserRoleEnum), default=UserRoleEnum.passenger, nullable=False)

    gender = Column(SQLEnum(GenderEnum), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    address = Column(Text, nullable=True)

    blood_group = Column(SQLEnum(BloodGroupEnum), nullable=True)
    health_conditions = Column(Text, nullable=True)
    emergency_contact = Column(String, nullable=True)
    next_of_kin_name = Column(String, nullable=True)
    next_of_kin_relationship = Column(String, nullable=True)

    is_active = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_suspended = Column(Boolean, default=False, nullable=False)

    is_driver = Column(Boolean, default=False, nullable=False)
    can_offer_rides = Column(Boolean, default=False, nullable=False)
    can_book_rides = Column(Boolean, default=True, nullable=False)

    nin = Column(String, unique=True, nullable=True)
    nin_verified = Column(Boolean, default=False, nullable=False)
    nin_verification_status = Column(
        SQLEnum(VerificationStatusEnum),
        default=VerificationStatusEnum.unverified,
        nullable=False,
    )
    nin_verification_notes = Column(Text, nullable=True)

    chattiness = Column(SQLEnum(ChattinessEnum), nullable=True)
    music_preference = Column(SQLEnum(MusicEnum), nullable=True)
    smoking_preference = Column(SQLEnum(SmokingEnum), nullable=True)
    pets_preference = Column(SQLEnum(PetsEnum), nullable=True)
    pet_friendly = Column(Boolean, default=False, nullable=False)

    photo_url = Column(String, nullable=True)
    otp_verification_id = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        )

    @property
    def profile_complete(self) -> bool:
        # User must have at least one contact method:
        # either email OR phone number.
        has_contact = bool(
            (self.email and self.email.strip())
            or
            (self.phone_number and self.phone_number.strip())
        )

        # These fields are required to complete the profile.
        required_fields = [
            self.full_name,
            self.address,
            self.date_of_birth,
            self.gender,
            self.blood_group,
            self.health_conditions,
            self.nin,
            self.photo_url,
        ]

        return has_contact and all(
            field is not None and str(field).strip() != ""
            for field in required_fields
        )
    

# Relationships
    driver_profile = relationship("DriverProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    offered_rides = relationship(
      "app.rides.models.Ride",
      foreign_keys="[Ride.driver_id]",
      back_populates="driver",
  )
    bookings = relationship("Booking", back_populates="passenger", cascade="all, delete-orphan")
    # bookings = relationship("app.bookings.models.Booking", back_populates="user", cascade="all, delete-orphan")
    cars = relationship("app.cars.models.Car", back_populates="owner", cascade="all, delete-orphan")    
    # rides = relationship(
    # "app.rides.models.Ride", back_populates="driver", overlaps="offered_rides"
# )
    # reviews_given = relationship("Review", foreign_keys="Review.reviewer_id", back_populates="reviewer")
    # reviews_received = relationship("Review", foreign_keys="Review.reviewee_id", back_populates="reviewee")

    payments = relationship(
        "app.payments.models.Payment",
        back_populates="user",
        cascade="all, delete-orphan",
    )
  



class DriverProfile(Base):
    __tablename__ = "driver_profiles"
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    car_make = Column(String, nullable=True)
    car_model = Column(String, nullable=True)
    car_year = Column(Integer, nullable=True)
    car_color = Column(String, nullable=True)
    plate_number = Column(String, unique=True, nullable=True)

    about_me = Column(Text, nullable=True)
    chattiness = Column(SQLEnum(ChattinessEnum), nullable=True)
    music = Column(SQLEnum(MusicEnum), nullable=True)
    smoking = Column(SQLEnum(SmokingEnum), nullable=True)
    pets = Column(SQLEnum(PetsEnum), nullable=True)

    license_number = Column(String, unique=True, nullable=True)
    license_expiry_date = Column(Date, nullable=True)
    license_front_url = Column(String, nullable=True)
    license_back_url = Column(String, nullable=True)
    license_photo_url = Column(String, nullable=True)
    license_verification_status = Column(
        SQLEnum(VerificationStatusEnum),
        default=VerificationStatusEnum.unverified,
        nullable=False,
    )
    license_verification_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="driver_profile")

    def is_complete(self) -> bool:
        required = [
            self.car_make,
            self.car_model,
            self.plate_number,
            self.license_number,
            self.license_expiry_date,
            self.license_front_url,
        ]
        return all(f is not None and f != "" for f in required)

