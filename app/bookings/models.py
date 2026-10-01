"""
app/bookings/models.py
"""

import enum
import uuid
from datetime import datetime, timezone, date
from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class BookingStatusEnum(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    TRIP_STARTED = "trip_started"
    TRIP_COMPLETED = "trip_completed"  # Fixed copy-paste value
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    passenger_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ride_id = Column(Integer, ForeignKey("rides.id"), nullable=False)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=True)

    travel_date = Column(Date, nullable=False)
    seats_booked = Column(Integer, default=1, nullable=False)
    fare = Column(Numeric(10, 2), nullable=False)

    # Added values_callable so SQLAlchemy sends 'pending' instead of 'PENDING'
    status = Column(
        SQLEnum(
            BookingStatusEnum,
            name="bookingstatusenum",
            values_callable=lambda x: [e.value for e in x]
        ),
        default=BookingStatusEnum.PENDING,
        nullable=False
    )

    driver_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    trip_started_at = Column(DateTime(timezone=True), nullable=True)
    trip_completed_at = Column(DateTime(timezone=True), nullable=True)
    funds_released_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    passenger = relationship("User", back_populates="bookings")
    ride = relationship("Ride", back_populates="bookings")
    car = relationship("app.cars.models.Car", back_populates="bookings")
    payments = relationship("Payment", back_populates="booking")

