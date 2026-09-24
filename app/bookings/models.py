"""
app/bookings/models.py
"""

from app.database import Base

import enum
from sqlalchemy import Column, Integer, Date, ForeignKey, Enum, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.cars.models import Car


class BookingStatusEnum(enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    ride_id = Column(UUID(as_uuid=True),
        ForeignKey("rides.id", ondelete="CASCADE"),
        nullable=False,
    )

    passenger_id = Column(UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    car_id = Column(
        Integer,
        ForeignKey("cars.id", ondelete="CASCADE"),
        nullable=False,
    )

    travel_date = Column(Date, nullable=False)
    seats_booked = Column(Integer, default=1, nullable=False)
    status = Column(
        Enum(BookingStatusEnum),
        default=BookingStatusEnum.pending,
        nullable=False,
    )

    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    ride = relationship("Ride", back_populates="bookings")
    passenger = relationship("User", back_populates="bookings")
    car = relationship(Car)