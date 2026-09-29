# """
# app/rides/models.py
# """
# import enum
# from datetime import datetime

# from sqlalchemy import (
#     ARRAY,
#     Boolean,
#     Column,
#     Date,
#     DateTime,
#     Enum,
#     Float,
#     ForeignKey,
#     Index,
#     Integer,
#     String,
#     Time,
    
# )
# from sqlalchemy.orm import relationship
# from sqlalchemy.dialects.postgresql import UUID
# from app.database import Base


# import json
# from sqlalchemy.types import TypeDecorator, TEXT
# from sqlalchemy.dialects.postgresql import ARRAY
# from sqlalchemy import Integer







# # ==========================================
# # ENUMS
# # ==========================================
# class RecurrenceType(str, enum.Enum):
#     DAILY = "daily"
#     WEEKLY = "weekly"
#     WEEKDAYS = "weekdays"
#     CUSTOM = "custom"


# class BookingStatus(str, enum.Enum):
#     PENDING = "pending"
#     CONFIRMED = "confirmed"
#     CANCELLED = "cancelled"
#     COMPLETED = "completed"


# # ==========================================
# # RIDE MODEL
# # ==========================================
# class IntegerArray(TypeDecorator):
#     """Uses ARRAY(Integer) on PostgreSQL, falls back to JSON/TEXT on SQLite."""
#     impl = TEXT
#     cache_ok = True

#     def load_dialect_impl(self, dialect):
#         if dialect.name == "postgresql":
#             return dialect.type_descriptor(ARRAY(Integer()))
#         return dialect.type_descriptor(TEXT())

#     def process_bind_param(self, value, dialect):
#         if dialect.name != "postgresql" and value is not None:
#             return json.dumps(value)
#         return value

#     def process_result_value(self, value, dialect):
#         if dialect.name != "postgresql" and value is not None:
#             return json.loads(value)
#         return value

# # In your Ride model:
# custom_days = Column(IntegerArray, nullable=True)

# class Ride(Base):
#     __tablename__ = "rides"

#     id = Column(Integer, primary_key=True, index=True)
#     driver_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
#     car_id = Column(Integer, ForeignKey("cars.id", ondelete="SET NULL"), nullable=True)

#     origin_city = Column(String, nullable=False, index=True)
#     pickup_location = Column(String, nullable=False, index=True)
#     pickup_lat = Column(Float, nullable=True)
#     pickup_lng = Column(Float, nullable=True)

#     destination_city = Column(String, nullable=False, index=True)
#     dropoff_location = Column(String, nullable=False, index=True)
#     dropoff_lat = Column(Float, nullable=True)
#     dropoff_lng = Column(Float, nullable=True)
    
#     pickup_time = Column(Time, nullable=False)
#     price_per_seat = Column(Float, nullable=False)
#     max_passengers = Column(Integer, nullable=False)
#     max_back_seat_passengers = Column(
#       Integer, nullable=True
#   )
#     instant_booking = Column(Boolean, default=False, nullable=False)
#     is_recurring = Column(Boolean, default=False)
#     recurrence_type = Column(Enum(RecurrenceType), nullable=True)
#     custom_days = Column(ARRAY(Integer), nullable=True)

#     start_date = Column(Date, nullable=True)
#     end_date = Column(Date, nullable=True)

#     is_active = Column(Boolean, default=True)
#     created_at = Column(DateTime, default=datetime.utcnow)

#     # Relationships
#     # driver = relationship("User", back_populates="rides_driven")
#     # car = relationship("app.cars.models.Car", back_populates="rides")
#     stopovers = relationship(
#         "Stopover",
#         back_populates="ride",
#         order_by="Stopover.order_index", # <-- Updated to 'order_index'
#     )
#     occurrences = relationship("RideOccurrence", back_populates="ride", cascade="all, delete-orphan")
#     # bookings = relationship("Booking", back_populates="ride")

#     # Inside class Ride(Base) in app/rides/models.py:

#     driver = relationship("app.models.User", back_populates="offered_rides")
#     car = relationship("app.cars.models.Car", back_populates="rides")
#     bookings = relationship("app.bookings.models.Booking", back_populates="ride", cascade="all, delete-orphan")

#     # Composite index for search speed
#     __table_args__ = (
#         Index(
#             "ix_rides_origin_destination_active",
#             "origin_city",
#             "destination_city",
#             "is_active",
#         ),
#     )

# # ==========================================
# # STOPOVER MODEL
# # ==========================================
# class Stopover(Base):
#     __tablename__ = "stopovers"

#     id = Column(Integer, primary_key=True, index=True)
#     ride_id = Column(Integer, ForeignKey("rides.id", ondelete="CASCADE"), nullable=False)

#     city_name = Column(String, nullable=False, index=True)
#     address = Column(String, nullable=True)
#     order_index = Column(Integer, nullable=True, default = 0.0)
#     price_from_origin = Column(Float, nullable=False)

#     # Relationships
#     ride = relationship("Ride", back_populates="stopovers")

#     # Composite index for stopover lookup
#     __table_args__ = (
#         Index("ix_stopovers_ride_city_order", "ride_id", "city_name", "order_index"),
#     )

# # ==========================================
# # RIDE OCCURRENCE MODEL
# # ==========================================
# class RideOccurrence(Base):
#     __tablename__ = "ride_occurrences"

#     id = Column(Integer, primary_key=True, index=True)
#     ride_id = Column(Integer, ForeignKey("rides.id", ondelete="CASCADE"), nullable=False)

#     date = Column(Date, nullable=False, index=True)
#     seats_remaining = Column(Integer, nullable=False)
#     is_cancelled = Column(Boolean, default=False)

#     # Relationships
#     ride = relationship("Ride", back_populates="occurrences")

#     # Composite index for date & available seat search filtering
#     __table_args__ = (
#         Index(
#             "ix_ride_occurrences_date_seats",
#             "ride_id",
#             "date",
#             "seats_remaining",
#         ),
#     )

import enum
import json
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    JSON,
    Time,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import TEXT, TypeDecorator

from app.database import Base


# ==========================================
# CUSTOM TYPES
# ==========================================
class IntegerArray(TypeDecorator):
    """Uses ARRAY(Integer) on PostgreSQL, falls back to JSON/TEXT on SQLite."""

    impl = TEXT
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(ARRAY(Integer()))
        return dialect.type_descriptor(TEXT())

    def process_bind_param(self, value, dialect):
        if dialect.name != "postgresql" and value is not None:
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if dialect.name != "postgresql" and value is not None:
            return json.loads(value)
        return value


# ==========================================
# ENUMS
# ==========================================
class RecurrenceType(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    WEEKDAYS = "weekdays"
    CUSTOM = "custom"


class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


# ==========================================
# RIDE MODEL
# ==========================================
class Ride(Base):
    __tablename__ = "rides"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    car_id = Column(Integer, ForeignKey("cars.id", ondelete="SET NULL"), nullable=True)

    origin_city = Column(String, nullable=False, index=True)
    pickup_location = Column(String, nullable=False, index=True)
    pickup_lat = Column(Float, nullable=True)
    pickup_lng = Column(Float, nullable=True)

    destination_city = Column(String, nullable=False, index=True)
    dropoff_location = Column(String, nullable=False, index=True)
    dropoff_lat = Column(Float, nullable=True)
    dropoff_lng = Column(Float, nullable=True)

    pickup_time = Column(Time, nullable=False)
    price_per_seat = Column(Float, nullable=False)
    max_passengers = Column(Integer, nullable=False)
    max_back_seat_passengers = Column(Integer, nullable=True)

    instant_booking = Column(Boolean, default=False, nullable=False)
    is_recurring = Column(Boolean, default=False)
    recurrence_type = Column(Enum(RecurrenceType), nullable=True)
    # custom_days = Column(IntegerArray, nullable=True)
    custom_days = Column(
    ARRAY(Integer()).with_variant(JSON, "sqlite"), 
    nullable=True
)

    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    driver = relationship("app.models.User", back_populates="offered_rides")
    car = relationship("app.cars.models.Car", back_populates="rides")
    stopovers = relationship(
        "Stopover",
        back_populates="ride",
        order_by="Stopover.order_index",
        cascade="all, delete-orphan",
    )
    occurrences = relationship(
        "RideOccurrence", back_populates="ride", cascade="all, delete-orphan"
    )
    bookings = relationship(
        "app.bookings.models.Booking",
        back_populates="ride",
        cascade="all, delete-orphan",
    )

    # Composite index for search speed
    __table_args__ = (
        Index(
            "ix_rides_origin_destination_active",
            "origin_city",
            "destination_city",
            "is_active",
        ),
    )


# ==========================================
# STOPOVER MODEL
# ==========================================
class Stopover(Base):
    __tablename__ = "stopovers"

    id = Column(Integer, primary_key=True, index=True)
    ride_id = Column(
        Integer, ForeignKey("rides.id", ondelete="CASCADE"), nullable=False
    )

    city_name = Column(String, nullable=False, index=True)
    address = Column(String, nullable=True)
    order_index = Column(Integer, nullable=True, default=0)
    price_from_origin = Column(Float, nullable=False)

    # Relationships
    ride = relationship("Ride", back_populates="stopovers")

    # Composite index for stopover lookup
    __table_args__ = (
        Index(
            "ix_stopovers_ride_city_order", "ride_id", "city_name", "order_index"
        ),
    )


# ==========================================
# RIDE OCCURRENCE MODEL
# ==========================================
class RideOccurrence(Base):
    __tablename__ = "ride_occurrences"

    id = Column(Integer, primary_key=True, index=True)
    ride_id = Column(
        Integer, ForeignKey("rides.id", ondelete="CASCADE"), nullable=False
    )

    date = Column(Date, nullable=False, index=True)
    seats_remaining = Column(Integer, nullable=False)
    is_cancelled = Column(Boolean, default=False)

    # Relationships
    ride = relationship("Ride", back_populates="occurrences")

    # Composite index for date & available seat search filtering
    __table_args__ = (
        Index(
            "ix_ride_occurrences_date_seats",
            "ride_id",
            "date",
            "seats_remaining",
        ),
    )