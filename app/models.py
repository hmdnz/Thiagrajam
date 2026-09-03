"""
app/models.py

Schema (single-role User + normalized DriverProfile for driver-only fields and travel preferences):
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey, TIMESTAMP, Date, DateTime,
    Enum, UniqueConstraint, Float, Text, text,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base
import enum


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
    unverified = "unverified"   # nothing submitted yet
    pending = "pending"         # selfie/document submitted, awaiting AI/manual check
    verified = "verified"       # confirmed match
    failed = "failed"           # AI check ran and did not match / was rejected


# ---- Driver Travel Preferences Enums ----

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
# User
# ---------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=True, index=True)
    phone_number = Column(String, unique=True, nullable=True, index=True)
    password = Column(String, nullable=False)

    is_verified = Column(Boolean, server_default="false", nullable=False)
    is_active = Column(Boolean, server_default="true", nullable=False)
    is_admin = Column(Boolean, server_default="false", nullable=False)

    otp_verification_id = Column(String, nullable=True)

    # ---- Common profile fields ----
    full_name = Column(String, nullable=True)
    address = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(Enum(GenderEnum), nullable=True)
    image = Column(String, nullable=True)  # Profile photo URL

    # ---- Next of kin / emergency ----
    next_of_kin_name = Column(String, nullable=True)
    next_of_kin_relationship = Column(String, nullable=True)
    emergency_contact = Column(String, nullable=True)

    # ---- Health ----
    blood_group = Column(Enum(BloodGroupEnum), nullable=True)
    health_conditions = Column(Text, nullable=True)

    # ---- Identity / NIN / selfie ----
    nin = Column(String, unique=True, nullable=True)
    photo_url = Column(String, nullable=True)  # NIN verification selfie photo

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

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(
        TIMESTAMP(timezone=True), nullable=False,
        server_default=text("now()"), onupdate=text("now()"),
    )

    # ---- Relationships ----
    posts = relationship("Post", back_populates="owner")
    driver_profile = relationship(
        "DriverProfile", back_populates="user",
        uselist=False, cascade="all, delete-orphan"
    )

    @property
    def is_passenger(self):
        return self.role == UserRoleEnum.passenger

    @property
    def is_driver(self):
        return self.role == UserRoleEnum.driver

    @is_passenger.setter
    def is_passenger(self, value):
        if value:
            self.role = UserRoleEnum.passenger

    @is_driver.setter
    def is_driver(self, value):
        if value:
            self.role = UserRoleEnum.driver

    def update_profile_complete(self):
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
        complete = all(field is not None for field in required_fields)

        if self.role == UserRoleEnum.driver:
            complete = complete and bool(self.driver_profile) and self.driver_profile.is_complete()

        self.profile_complete = complete
        return self.profile_complete


# ---------------------------------------------------------------
# DriverProfile
# ---------------------------------------------------------------

class DriverProfile(Base):
    __tablename__ = "driver_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )

    license_number = Column(String, unique=True, nullable=True)
    license_photo_url = Column(String, nullable=True)
    license_expiry_date = Column(Date, nullable=True)
    about_me = Column(Text, nullable=True)

    # ---- Driver Travel Preferences ----
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

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(
        TIMESTAMP(timezone=True), nullable=False,
        server_default=text("now()"), onupdate=text("now()"),
    )

    user = relationship("User", back_populates="driver_profile")

    # ---- Forwarding properties for non-redundant access ----
    @property
    def gender(self):
        return self.user.gender if self.user else None

    @gender.setter
    def gender(self, value):
        if self.user:
            self.user.gender = value

    @property
    def image(self):
        return self.user.image if self.user else None

    @image.setter
    def image(self, value):
        if self.user:
            self.user.image = value

    @property
    def driving_licence_no(self):
        return self.license_number

    @driving_licence_no.setter
    def driving_licence_no(self, value):
        self.license_number = value

    def is_complete(self) -> bool:
        return all([
            self.license_number,
            self.license_photo_url,
            self.license_expiry_date,
            self.about_me,
        ])


# ---------------------------------------------------------------
# Post & PhoneVerification
# ---------------------------------------------------------------

class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, nullable=False)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    published = Column(Boolean, server_default='TRUE', nullable=False)
    rating = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    owner = relationship("User", back_populates="posts")


class PhoneVerification(Base):
    __tablename__ = "phone_verifications"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, nullable=False, index=True)
    otp_hash = Column(String, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())