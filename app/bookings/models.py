"""
app/bookings/models.py
"""

from sqlalchemy import (
    Column,
    Integer,
    Date,
    ForeignKey,
    TIMESTAMP,
    Enum,
    Numeric,
    text,
)
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class BookingStatusEnum(enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    passenger_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # CHANGED: was car_id. A booking is now against a
    # published Ride, not a bare Car — the ride carries the
    # route, price, and capacity that used to be missing.
    ride_id = Column(
        Integer,
        ForeignKey(
            "rides.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # Which occurrence of the ride (matters for recurring
    # rides — a passenger books one specific date).
    ride_date = Column(
        Date,
        nullable=False,
    )

    seats_booked = Column(
        Integer,
        nullable=False,
        default=1,
    )

    # CHANGED: snapshotted from ride.price_per_seat at
    # booking time, server-side — never taken from the
    # passenger's request. This is what actually got charged,
    # even if the driver changes the ride's price later.
    fare = Column(
        Numeric(10, 2),
        nullable=False,
    )

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

    passenger = relationship("User")

    ride = relationship("Ride")