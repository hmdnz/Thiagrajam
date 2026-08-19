"""
app/models.py

New schema (replaces the old is_passenger / is_driver boolean flags on User):
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, ForeignKey, TIMESTAMP, Date, DateTime,
    Enum, UniqueConstraint, text,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base
import enum

# Define Role enum - SINGLE DEFINITION
class UserRoleEnum(enum.Enum):
    passenger = "passenger"
    driver = "driver"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=True, index=True)
    phone_number = Column(String, unique=True, nullable=True, index=True)
    password = Column(String, nullable=False)

    # Has the person proven they own this email/phone?
    is_verified = Column(Boolean, server_default="false", nullable=False)
    is_active = Column(Boolean, server_default="true", nullable=False)

    # ---- Common profile fields ----
    full_name = Column(String, nullable=True)
    address = Column(String, nullable=True)
    emergency_contact = Column(String, nullable=True)
    photo_url = Column(String, nullable=True)
    nin = Column(String, unique=True, nullable=True)
    date_of_birth = Column(Date, nullable=True)

    # Single role field - use the enum
    role = Column(Enum(UserRoleEnum), default=UserRoleEnum.passenger, nullable=False)
    
    # Profile completion flag
    profile_complete = Column(Boolean, server_default="false", nullable=False)

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(
        TIMESTAMP(timezone=True), nullable=False,
        server_default=text("now()"), onupdate=text("now()"),
    )

    # Relationships
    posts = relationship("Post", back_populates="owner")
    
    # Computed properties for backward compatibility
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
    
    # Check if profile is complete based on required fields
    def update_profile_complete(self):
        required_fields = [
            self.full_name,
            self.address,
            self.phone_number,
            self.emergency_contact,
            self.date_of_birth
        ]
        # For drivers, add additional requirements
        if self.role == UserRoleEnum.driver:
            required_fields.extend([self.nin, self.photo_url])
        
        self.profile_complete = all(field is not None for field in required_fields)
        return self.profile_complete


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