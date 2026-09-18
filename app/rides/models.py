"""
app/rides/models.py
"""

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, TIMESTAMP, Time, Numeric, Date, Float, text
from sqlalchemy.orm import relationship

from app.database import Base


class Ride(Base):
    __tablename__ = "rides"

    id = Column(Integer, primary_key=True, index=True)

    driver_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    car_id = Column(
        Integer,
        ForeignKey("cars.id", ondelete="CASCADE"),
        nullable=False,
    )

    # --- Macro Journey (City Level) ---
    origin_city = Column(String, nullable=False, index=True)      # e.g., "Kano"
    origin_state = Column(String, nullable=True)                  # e.g., "Kano"
    destination_city = Column(String, nullable=False, index=True) # e.g., "Abuja"
    destination_state = Column(String, nullable=True)             # e.g., "FCT"


    pickup_location = Column(String, nullable=False)
    pickup_lat = Column(Float, nullable=True)
    pickup_lng = Column(Float, nullable=True)

    dropoff_location = Column(String, nullable=False)
    dropoff_lat = Column(Float, nullable=True)
    dropoff_lng = Column(Float, nullable=True)

    pickup_time = Column(Time, nullable=False)
    is_recurring = Column(Boolean, default=False, nullable=False)

    max_passengers = Column(Integer, nullable=False)
    max_back_seat_passengers = Column(Integer, nullable=True)

    instant_booking = Column(Boolean, default=False, nullable=False)
    price_per_seat = Column(Numeric(10, 2), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

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