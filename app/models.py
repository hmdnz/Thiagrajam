from app.database import Base
import enum
from uuid import uuid4
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

# Base = declarative_base()


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
    quiet = "quiet"
    moderate = "moderate"
    chatty = "chatty"


class MusicEnum(str, enum.Enum):
    no_music = "no_music"
    pop = "pop"
    rock = "rock"
    afrobeats = "afrobeats"
    classical = "classical"
    any = "any"


class SmokingEnum(str, enum.Enum):
    no_smoking = "no_smoking"
    vape_only = "vape_only"
    allowed = "allowed"


class PetsEnum(str, enum.Enum):
    no_pets = "no_pets"
    small_pets = "small_pets"
    allowed = "allowed"


# ===============================================================
# MODELS
# ===============================================================

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    published = Column(Boolean, default=True, nullable=False)
    rating = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    full_name = Column(String, nullable=True)
    email = Column(String, unique=True, nullable=True, index=True)
    phone_number = Column(String, unique=True, nullable=True, index=True)
    password = Column(String, nullable=False)
    role = Column(SQLEnum(UserRoleEnum), default=UserRoleEnum.passenger, nullable=False)

    # Demographic & Personal Info
    gender = Column(SQLEnum(GenderEnum), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    address = Column(Text, nullable=True)

    # Health & Emergency Contact
    blood_group = Column(SQLEnum(BloodGroupEnum), nullable=True)
    health_conditions = Column(Text, nullable=True)
    emergency_contact = Column(String, nullable=True)
    next_of_kin_name = Column(String, nullable=True)
    next_of_kin_relationship = Column(String, nullable=True)

    # General Account Status & Safety Flags
    is_active = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_suspended = Column(Boolean, default=False, nullable=False)

    # Driver Access Control Flags
    is_driver = Column(Boolean, default=False, nullable=False)
    can_offer_rides = Column(Boolean, default=False, nullable=False)

    # National Identification Number (NIN)
    nin = Column(String, unique=True, nullable=True)
    nin_verified = Column(Boolean, default=False, nullable=False)
    nin_verification_status = Column(
        SQLEnum(VerificationStatusEnum),
        default=VerificationStatusEnum.unverified,
        nullable=False,
    )
    nin_verification_notes = Column(Text, nullable=True)

    # Shared Social / Travel Preferences
    chattiness = Column(SQLEnum(ChattinessEnum), nullable=True)
    music_preference = Column(SQLEnum(MusicEnum), nullable=True)
    smoking_preference = Column(SQLEnum(SmokingEnum), nullable=True)
    pets_preference = Column(SQLEnum(PetsEnum), nullable=True)
    pet_friendly = Column(Boolean, default=False, nullable=False)

    # Profile & Security Attributes
    photo_url = Column(String, nullable=True)
    otp_verification_id = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Dynamic Profile Completion Property
    @property
    def profile_complete(self) -> bool:
        """
        Calculates whether all required profile fields have been provided.
        Evaluated dynamically during Pydantic serialization.
        """
        required_fields = [
            self.email,
            self.phone_number,
            self.full_name,
            self.address,
            self.date_of_birth,
            self.gender,
            self.blood_group,
            self.health_conditions,
            self.nin,
            self.photo_url,
        ]

        return all(
            field is not None and str(field).strip() != ""
            for field in required_fields
        )

    # Relationships
    driver_profile = relationship("DriverProfile", back_populates="user", uselist=False)
    cars = relationship("Car", back_populates="owner")
    bookings = relationship("Booking", back_populates="passenger")
    rides = relationship("Ride", back_populates="driver")
    rides_driven = relationship("Ride", back_populates="driver", overlaps="rides")
   
class DriverProfile(Base):
    __tablename__ = "driver_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Vehicle Specifications
    car_make = Column(String, nullable=True)
    car_model = Column(String, nullable=True)
    car_year = Column(Integer, nullable=True)
    car_color = Column(String, nullable=True)
    plate_number = Column(String, unique=True, nullable=True)

    # Driver Details & Preferences
    about_me = Column(Text, nullable=True)
    chattiness = Column(SQLEnum(ChattinessEnum), nullable=True)
    music = Column(SQLEnum(MusicEnum), nullable=True)
    smoking = Column(SQLEnum(SmokingEnum), nullable=True)
    pets = Column(SQLEnum(PetsEnum), nullable=True)

    # Driver Licensing & Legal
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

    # Relationships
    user = relationship("User", back_populates="driver_profile")

    def is_complete(self) -> bool:
        """Determines if the driver has provided all required verification fields."""
        required = [
            self.car_make,
            self.car_model,
            self.plate_number,
            self.license_number,
            self.license_expiry_date,
            self.license_front_url,
        ]
        return all(f is not None and f != "" for f in required)