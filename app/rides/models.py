"""
app/rides/models.py
"""

# app/rides/models.py

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Date,
    Boolean,
    Numeric,
    Time,
    DateTime,
    ForeignKey,
)

from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base

class Ride(Base):
    __tablename__ = "rides"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    car_id = Column(Integer, ForeignKey("cars.id", ondelete="CASCADE"), nullable=False)
    origin_city = Column(String, nullable=False)
    destination_city = Column(String, nullable=False)
    pickup_location = Column(String, nullable=False)
    pickup_lat = Column(Float)
    pickup_lng = Column(Float)
    dropoff_location = Column(String, nullable=False)
    dropoff_lat = Column(Float)
    dropoff_lng = Column(Float)
    pickup_time = Column(Time, nullable=False)
    is_recurring = Column(Boolean, nullable=False)
    max_passengers = Column(Integer, nullable=False)
    max_back_seat_passengers = Column(Integer)
    instant_booking = Column(Boolean, nullable=False)
    price_per_seat = Column(Numeric(10, 2), nullable=False)
    is_active = Column(Boolean, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    # FIX THIS LINE: Ensure closing parenthesis ')' is present
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    # Relationships
    driver = relationship("User", back_populates="rides")
    car = relationship("Car", back_populates="rides")
    occurrences = relationship("RideOccurrence", back_populates="ride", cascade="all, delete-orphan")
    stopovers = relationship("Stopover", back_populates="ride", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="ride", cascade="all, delete-orphan")


class RideOccurrence(Base):
    __tablename__ = "ride_occurrences"

    id = Column(Integer, primary_key=True, index=True)

    ride_id = Column(
        Integer,
        ForeignKey("rides.id", ondelete="CASCADE"),
        nullable=False,
    )

    date = Column(Date, nullable=False)
    seats_remaining = Column(Integer, nullable=False)

    ride = relationship("Ride", back_populates="occurrences")


class Stopover(Base):
    __tablename__ = "stopovers"

    id = Column(Integer, primary_key=True, index=True)

    ride_id = Column(
        Integer,
        ForeignKey("rides.id", ondelete="CASCADE"),
        nullable=False,
    )

    location_name = Column(String, nullable=False)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    price_from_pickup = Column(Numeric(10, 2), nullable=True)

    ride = relationship("Ride", back_populates="stopovers")