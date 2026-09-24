from app.database import Base

from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base  # Adjust import path if necessary


class Car(Base):
    __tablename__ = "cars"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(UUID(as_uuid=True), ForeignKey("users.id", 
   ondelete="CASCADE"), nullable=False)
    make = Column(String, nullable=False)
    model = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    color = Column(String, nullable=False)
    plate_number = Column(String, nullable=True)
    capacity = Column(Integer, default=4, nullable=False)

    is_tinted = Column(Boolean, default=False)
    has_wifi = Column(Boolean, default=False)
    has_air_conditioning = Column(Boolean, default=False)
    has_power_outlets = Column(Boolean, default=False)
    smoking_allowed = Column(Boolean, default=False)
    pets_allowed = Column(Boolean, default=False)
    wheelchair_accessible = Column(Boolean, default=False)

    created_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Relationships
    owner = relationship("User", back_populates="cars")

    photos = relationship(
        "CarPhoto", back_populates="car", cascade="all, delete-orphan"
    )

    rides = relationship(
        "Ride", back_populates="car", cascade="all, delete-orphan"
    )


class CarPhoto(Base):
    __tablename__ = "car_photos"

    id = Column(Integer, primary_key=True, index=True)
    car_id = Column(
        Integer, ForeignKey("cars.id", ondelete="CASCADE"), nullable=False
    )
    photo_url = Column(String, nullable=False)

    created_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    car = relationship("Car", back_populates="photos")