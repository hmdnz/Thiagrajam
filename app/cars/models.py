"""
app/cars/models.py

Car and CarPhoto tables.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    TIMESTAMP,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Car(Base):
    __tablename__ = "cars"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    driver_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------
    # BASIC VEHICLE INFO
    # ------------------------------------------------------

    make = Column(
        String,
        nullable=False,
    )

    model = Column(
        String,
        nullable=False,
    )

    year = Column(
        Integer,
        nullable=False,
    )

    color = Column(
        String,
        nullable=False,
    )

    plate_number = Column(
        String,
        unique=True,
        nullable=False,
        index=True,
    )

    capacity = Column(
        Integer,
        nullable=False,
        default=4,
    )

    # ------------------------------------------------------
    # AMENITIES
    # Each is a simple boolean flag. Add more here later by
    # following the same pattern — one Column per amenity.
    # ------------------------------------------------------

    is_tinted = Column(
        Boolean,
        server_default="false",
        nullable=False,
    )

    has_wifi = Column(
        Boolean,
        server_default="false",
        nullable=False,
    )

    has_air_conditioning = Column(
        Boolean,
        server_default="false",
        nullable=False,
    )

    has_power_outlets = Column(
        Boolean,
        server_default="false",
        nullable=False,
    )

    smoking_allowed = Column(
        Boolean,
        server_default="false",
        nullable=False,
    )

    pets_allowed = Column(
        Boolean,
        server_default="false",
        nullable=False,
    )

    wheelchair_accessible = Column(
        Boolean,
        server_default="false",
        nullable=False,
    )

    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # ------------------------------------------------------
    # RELATIONSHIPS
    # ------------------------------------------------------

    driver = relationship("User")

    photos = relationship(
        "CarPhoto",
        back_populates="car",
        cascade="all, delete-orphan",
    )


class CarPhoto(Base):
    """
    A single photo of a car. A car can have several — this is
    a separate table (rather than one photo_url column on Car)
    so the number of photos isn't fixed.
    """

    __tablename__ = "car_photos"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    car_id = Column(
        Integer,
        ForeignKey(
            "cars.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    photo_url = Column(
        String,
        nullable=False,
    )

    is_primary = Column(
        Boolean,
        server_default="false",
        nullable=False,
    )

    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    car = relationship(
        "Car",
        back_populates="photos",
    )