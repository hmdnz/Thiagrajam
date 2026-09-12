"""
app/rides/models.py

A Ride is a trip a driver publishes. It always has at least
one date (RideOccurrence) — recurring rides just have more
than one, up to 10. Search always joins through
RideOccurrence, so non-recurring and recurring rides are
queried the same way.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Numeric,
    Date,
    Time,
    Float,
    ForeignKey,
    TIMESTAMP,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Ride(Base):
    __tablename__ = "rides"

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

    car_id = Column(
        Integer,
        ForeignKey(
            "cars.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------
    # ROUTE
    # ------------------------------------------------------

    pickup_location = Column(
        String,
        nullable=False,
    )

    pickup_lat = Column(
        Float,
        nullable=True,
    )

    pickup_lng = Column(
        Float,
        nullable=True,
    )

    dropoff_location = Column(
        String,
        nullable=False,
    )

    dropoff_lat = Column(
        Float,
        nullable=True,
    )

    dropoff_lng = Column(
        Float,
        nullable=True,
    )

    # ------------------------------------------------------
    # SCHEDULE
    # Actual date(s) live in RideOccurrence, not here — see
    # module docstring.
    # ------------------------------------------------------

    pickup_time = Column(
        Time,
        nullable=False,
    )

    is_recurring = Column(
        Boolean,
        server_default="false",
        nullable=False,
    )

    # ------------------------------------------------------
    # CAPACITY
    # ------------------------------------------------------

    max_passengers = Column(
        Integer,
        nullable=False,
    )

    max_back_seat_passengers = Column(
        Integer,
        nullable=True,
    )

    # ------------------------------------------------------
    # BOOKING BEHAVIOUR
    # ------------------------------------------------------

    instant_booking = Column(
        Boolean,
        server_default="false",
        nullable=False,
    )

    price_per_seat = Column(
        Numeric(10, 2),
        nullable=False,
    )

    # ------------------------------------------------------
    # RETURN RIDE
    # Self-referential — links a ride to its return leg.
    # ------------------------------------------------------

    return_ride_id = Column(
        Integer,
        ForeignKey(
            "rides.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    # ------------------------------------------------------
    # STATUS
    # ------------------------------------------------------

    is_active = Column(
        Boolean,
        server_default="true",
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

    car = relationship("Car")

    stopovers = relationship(
        "RideStopover",
        back_populates="ride",
        cascade="all, delete-orphan",
        order_by="RideStopover.sequence",
    )

    occurrences = relationship(
        "RideOccurrence",
        back_populates="ride",
        cascade="all, delete-orphan",
    )

    return_ride = relationship(
        "Ride",
        remote_side=[id],
    )


class RideStopover(Base):
    """
    A stop along the route. Order matters (sequence), since
    these are shown to passengers as a list of cities/points
    along the way.
    """

    __tablename__ = "ride_stopovers"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    ride_id = Column(
        Integer,
        ForeignKey(
            "rides.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    location = Column(
        String,
        nullable=False,
    )

    lat = Column(
        Float,
        nullable=True,
    )

    lng = Column(
        Float,
        nullable=True,
    )

    sequence = Column(
        Integer,
        nullable=False,
        default=0,
    )

    ride = relationship(
        "Ride",
        back_populates="stopovers",
    )


class RideOccurrence(Base):
    """
    One concrete date a ride runs on. A non-recurring ride
    has exactly one row here; a recurring ride has up to 10
    (enforced in the schema, not the DB).
    """

    __tablename__ = "ride_occurrences"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    ride_id = Column(
        Integer,
        ForeignKey(
            "rides.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    date = Column(
        Date,
        nullable=False,
    )

    ride = relationship(
        "Ride",
        back_populates="occurrences",
    )