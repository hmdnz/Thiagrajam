from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, Enum, Float, text
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

    id = Column(Integer, primary_key=True, index=True)
    passenger_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    car_id = Column(Integer, ForeignKey("cars.id", ondelete="CASCADE"), nullable=False)
    pickup_location = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    fare = Column(Float, nullable=False)
    seats_booked = Column(Integer, nullable=False, default=1)
    status = Column(Enum(BookingStatusEnum), default=BookingStatusEnum.pending, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

    passenger = relationship("User")
    car = relationship("Car")