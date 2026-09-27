"""app/bookings/models.py"""

import enum
from sqlalchemy import Column, Integer, Date, ForeignKey, Enum, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class BookingStatusEnum(enum.Enum):
  pending = "pending"
  confirmed = "confirmed"
  cancelled = "cancelled"


class Booking(Base):
  __tablename__ = "bookings"

  id = Column(Integer, primary_key=True, index=True)

  ride_id = Column(
      Integer, ForeignKey("rides.id", ondelete="CASCADE"), nullable=False
  )

    

  passenger_id = Column(
      UUID(as_uuid=True),
      ForeignKey("users.id", ondelete="CASCADE"),
      nullable=False,
  )

  car_id = Column(
      Integer, ForeignKey("cars.id", ondelete="CASCADE"), nullable=False
  )

  # If this self-referential FK is intended, it must match integer type of bookings.id
  booking_id = Column(
      Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=True
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

  # RELATIONSHIPS (Must be indented inside the Booking class)
  passenger = relationship("app.models.User", back_populates="bookings")
#   user = relationship("app.models.User", back_populates="bookings_as_user")
  ride = relationship("app.rides.models.Ride", back_populates="bookings")
  car = relationship("app.cars.models.Car", back_populates="bookings")

  payments = relationship(
      "app.payments.models.Payment",
      back_populates="booking",
      cascade="all, delete-orphan",
  )