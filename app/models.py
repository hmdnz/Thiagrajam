"""
app/models.py

Schema (single-role User + normalized DriverProfile for driver-only fields):
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
    # A user is either a passenger or a driver at any given time.
    passenger = "passenger"
    driver = "driver"


class BloodGroupEnum(enum.Enum):
    # Standard blood types, plus "unknown" for users who don't know theirs.
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
    # Shared status enum used for both NIN verification and licence verification.
    unverified = "unverified"   # nothing submitted yet
    pending = "pending"         # selfie/document submitted, awaiting AI/manual check
    verified = "verified"       # confirmed match
    failed = "failed"           # AI check ran and did not match / was rejected


# ---------------------------------------------------------------
# User
# ---------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=True, index=True)
    phone_number = Column(String, unique=True, nullable=True, index=True)
    password = Column(String, nullable=False)

    # Has the person proven they own this email/phone?
    is_verified = Column(Boolean, server_default="false", nullable=False)
    is_active = Column(Boolean, server_default="true", nullable=False)

    # Grants access to admin-only endpoints (NIN/licence approval, etc.).
    # There is no self-service way to set this — promote users manually via:
    #   UPDATE users SET is_admin = true WHERE id = <id>;
    is_admin = Column(Boolean, server_default="false", nullable=False)

    # Kudisms verification_id for the OTP currently in flight, if any.
    # Set when send_kudisms_otp() succeeds; cleared to NULL once verify-otp
    # succeeds (or when a new OTP is sent, since it replaces the old one).
    otp_verification_id = Column(String, nullable=True)

    # ---- Common profile fields ----
    full_name = Column(String, nullable=True)
    address = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)

    # ---- Next of kin / emergency ----
    next_of_kin_name = Column(String, nullable=True)
    next_of_kin_relationship = Column(String, nullable=True)
    # `emergency_contact` doubles as the next-of-kin's phone number —
    # "number to call in case of emergency".
    emergency_contact = Column(String, nullable=True)

    # ---- Health ----
    blood_group = Column(Enum(BloodGroupEnum), nullable=True)
    health_conditions = Column(Text, nullable=True)  # free text, optional — "if any"

    # ---- Identity / NIN / selfie ----
    nin = Column(String, unique=True, nullable=True)
    photo_url = Column(String, nullable=True)  # the camera selfie

    # Tracks whether an admin has checked the submitted NIN against the selfie.
    nin_verification_status = Column(
        Enum(VerificationStatusEnum),
        default=VerificationStatusEnum.unverified,
        server_default=VerificationStatusEnum.unverified.value,
        nullable=False,
    )
    nin_verified_at = Column(TIMESTAMP(timezone=True), nullable=True)
    nin_match_score = Column(Float, nullable=True)          # AI confidence score, 0-1 (future use)
    nin_verification_notes = Column(String, nullable=True)  # e.g. failure reason shown to the user

    # Single role field - use the enum. Determines whether this account
    # currently operates as a passenger or a driver.
    role = Column(Enum(UserRoleEnum), default=UserRoleEnum.passenger, nullable=False)

    # True once all required profile fields (and, for drivers, the
    # DriverProfile fields) are filled in. Recomputed by update_profile_complete().
    profile_complete = Column(Boolean, server_default="false", nullable=False)

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(
        TIMESTAMP(timezone=True), nullable=False,
        server_default=text("now()"), onupdate=text("now()"),
    )

    # ---- Relationships ----
    posts = relationship("Post", back_populates="owner")
    # One-to-one: only present once the user has switched to driver role.
    # cascade="all, delete-orphan" means deleting the user also deletes their DriverProfile.
    driver_profile = relationship(
        "DriverProfile", back_populates="user",
        uselist=False, cascade="all, delete-orphan"
    )

    # ---- Computed properties for backward compatibility ----
    # These let old code that checked `user.is_passenger` / `user.is_driver`
    # as booleans keep working even though role is now a single enum field.
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
        """Recomputes profile_complete. Call this after any profile edit,
        then db.commit(). Health conditions are intentionally excluded —
        they're optional ("if any"), never a completion requirement."""
        required_fields = [
            self.full_name,
            self.address,
            self.phone_number,
            self.date_of_birth,
            self.next_of_kin_name,
            self.emergency_contact,     # next-of-kin phone
            self.blood_group,
            self.nin,
            self.photo_url,             # the selfie
        ]
        complete = all(field is not None for field in required_fields)

        # Drivers have an extra bar to clear: their DriverProfile
        # (licence number, photo, expiry) must also be filled in.
        if self.role == UserRoleEnum.driver:
            complete = complete and bool(self.driver_profile) and self.driver_profile.is_complete()

        self.profile_complete = complete
        return self.profile_complete


# ---------------------------------------------------------------
# DriverProfile
# ---------------------------------------------------------------
# Kept separate from User so passenger accounts never carry unused
# driver-only columns, and so a user can switch roles cleanly.

class DriverProfile(Base):
    __tablename__ = "driver_profiles"

    id = Column(Integer, primary_key=True, index=True)
    # One DriverProfile per user — enforced by unique=True.
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )

    license_number = Column(String, unique=True, nullable=True)
    license_photo_url = Column(String, nullable=True)
    license_expiry_date = Column(Date, nullable=True)

    # Tracks whether an admin has checked the licence photo/number
    # against the vehicle documents.
    license_verification_status = Column(
        Enum(VerificationStatusEnum),
        default=VerificationStatusEnum.unverified,
        server_default=VerificationStatusEnum.unverified.value,
        nullable=False,
    )
    license_verification_notes = Column(String, nullable=True)  # e.g. failure reason shown to the user

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(
        TIMESTAMP(timezone=True), nullable=False,
        server_default=text("now()"), onupdate=text("now()"),
    )

    user = relationship("User", back_populates="driver_profile")

    def is_complete(self) -> bool:
        # "Complete" means there's something for an admin to review —
        # NOT that it's been verified yet. Verification is a separate step.
        return all([
            self.license_number,
            self.license_photo_url,
            self.license_expiry_date,
        ])


# ---------------------------------------------------------------
# Post
# ---------------------------------------------------------------
# Unrelated to the profile/verification system above — kept as-is.

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


# ---------------------------------------------------------------
# PhoneVerification
# ---------------------------------------------------------------
# Legacy table from an earlier self-generated-OTP approach, superseded
# by Kudisms managing OTPs itself (see User.otp_verification_id above).
# Left in place in case existing rows/data depend on it.

class PhoneVerification(Base):
    __tablename__ = "phone_verifications"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String, nullable=False, index=True)
    otp_hash = Column(String, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())