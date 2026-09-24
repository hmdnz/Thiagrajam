# # """
# # app/cars/models.py

# # Car and CarPhoto tables.
# # """

# # from sqlalchemy import (
# #     Column,
# #     Integer,
# #     String,
# #     Boolean,
# #     ForeignKey,
# #     TIMESTAMP,
# #     text,
# # )
# # from sqlalchemy.orm import relationship

# # from app.database import Base


# # class Car(Base):
# #     __tablename__ = "cars"

# #     id = Column(
# #         Integer,
# #         primary_key=True,
# #         index=True,
# #     )

# #     driver_id = Column(
# #         Integer,
# #         ForeignKey(
# #             "users.id",
# #             ondelete="CASCADE",
# #         ),
# #         nullable=False,
# #         index=True,
# #     )

# #     # ------------------------------------------------------
# #     # BASIC VEHICLE INFO
# #     # ------------------------------------------------------

# #     make = Column(
# #         String,
# #         nullable=False,
# #     )

# #     model = Column(
# #         String,
# #         nullable=False,
# #     )

# #     year = Column(
# #         Integer,
# #         nullable=False,
# #     )

# #     color = Column(
# #         String,
# #         nullable=False,
# #     )

# #     plate_number = Column(
# #         String,
# #         unique=True,
# #         nullable=False,
# #         index=True,
# #     )

# #     capacity = Column(
# #         Integer,
# #         nullable=False,
# #         default=4,
# #     )

# #     # ------------------------------------------------------
# #     # AMENITIES
# #     # ------------------------------------------------------

# #     is_tinted = Column(
# #         Boolean,
# #         server_default="false",
# #         nullable=False,
# #     )

# #     has_wifi = Column(
# #         Boolean,
# #         server_default="false",
# #         nullable=False,
# #     )

# #     has_air_conditioning = Column(
# #         Boolean,
# #         server_default="false",
# #         nullable=False,
# #     )

# #     has_power_outlets = Column(
# #         Boolean,
# #         server_default="false",
# #         nullable=False,
# #     )

# #     smoking_allowed = Column(
# #         Boolean,
# #         server_default="false",
# #         nullable=False,
# #     )

# #     pets_allowed = Column(
# #         Boolean,
# #         server_default="false",
# #         nullable=False,
# #     )

# #     wheelchair_accessible = Column(
# #         Boolean,
# #         server_default="false",
# #         nullable=False,
# #     )

# #     created_at = Column(
# #         TIMESTAMP(timezone=True),
# #         nullable=False,
# #         server_default=text("now()"),
# #     )

# #     # ------------------------------------------------------
# #     # RELATIONSHIPS
# #     # ------------------------------------------------------

# #     owner = relationship(
# #         "User",
# #         back_populates="cars",
# #     )

# #     photos = relationship(
# #         "CarPhoto",
# #         back_populates="car",
# #         cascade="all, delete-orphan",
# #     )

# #     rides = relationship(
# #         "Ride",
# #         back_populates="car",
# #         cascade="all, delete-orphan",
# #     )


# # class CarPhoto(Base):
# #     """
# #     A single photo of a car.
# #     """

# #     __tablename__ = "car_photos"

# #     id = Column(
# #         Integer,
# #         primary_key=True,
# #         index=True,
# #     )

# #     car_id = Column(
# #         Integer,
# #         ForeignKey(
# #             "cars.id",
# #             ondelete="CASCADE",
# #         ),
# #         nullable=False,
# #         index=True,
# #     )

# #     photo_url = Column(
# #         String,
# #         nullable=False,
# #     )

# #     is_primary = Column(
# #         Boolean,
# #         server_default="false",
# #         nullable=False,
# #     )

# #     created_at = Column(
# #         TIMESTAMP(timezone=True),
# #         nullable=False,
# #         server_default=text("now()"),
# #     )

# #     car = relationship(
# #         "Car",
# #         back_populates="photos",
# #     )





# from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
# from sqlalchemy.orm import relationship
# from datetime import datetime
# from app.database import Base


# class Car(Base):
#     __tablename__ = "cars"

#     id = Column(Integer, primary_key=True, index=True)
#     driver_id = Column(
#         Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
#     )
#     make = Column(String, nullable=False)
#     model = Column(String, nullable=False)
#     year = Column(Integer, nullable=False)
#     color = Column(String, nullable=False)
#     license_plate = Column(String, nullable=True)
#     capacity = Column(Integer, default=4, nullable=False)

#     is_tinted = Column(Boolean, default=False)
#     has_wifi = Column(Boolean, default=False)
#     has_air_conditioning = Column(Boolean, default=False)
#     has_power_outlets = Column(Boolean, default=False)
#     smoking_allowed = Column(Boolean, default=False)
#     pets_allowed = Column(Boolean, default=False)
#     wheelchair_accessible = Column(Boolean, default=False)

#     created_at = Column(
#         DateTime(timezone=True), default=datetime.utcnow, nullable=False
#     )

#     photos = relationship(
#         "CarPhoto", back_populates="car", cascade="all, delete-orphan"
#     )

#     @property
#     def plate_number(self) -> str | None:
#         """Exposes license_plate as plate_number for clean Pydantic schema mapping."""
#         return self.license_plate


# class CarPhoto(Base):
#     __tablename__ = "car_photos"

#     id = Column(Integer, primary_key=True, index=True)
#     car_id = Column(
#         Integer, ForeignKey("cars.id", ondelete="CASCADE"), nullable=False
#     )
#     photo_url = Column(String, nullable=False)
#     is_primary = Column(Boolean, default=False)
#     created_at = Column(
#         DateTime(timezone=True), default=datetime.utcnow, nullable=False
#     )

#     car = relationship("Car", back_populates="photos")


from app.database import Base

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


# class Car(Base):
#     __tablename__ = "cars"

#     id = Column(Integer, primary_key=True, index=True)
#     driver_id = Column(
#         Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
#     )
#     make = Column(String, nullable=False)
#     model = Column(String, nullable=False)
#     year = Column(Integer, nullable=False)
#     color = Column(String, nullable=False)
#     license_plate = Column(String, nullable=True)
#     capacity = Column(Integer, default=4, nullable=False)

#     is_tinted = Column(Boolean, default=False)
#     has_wifi = Column(Boolean, default=False)
#     has_air_conditioning = Column(Boolean, default=False)
#     has_power_outlets = Column(Boolean, default=False)
#     smoking_allowed = Column(Boolean, default=False)
#     pets_allowed = Column(Boolean, default=False)
#     wheelchair_accessible = Column(Boolean, default=False)

#     created_at = Column(
#         DateTime(timezone=True), default=datetime.utcnow, nullable=False
#     )

#     photos = relationship(
#         "CarPhoto", back_populates="car", cascade="all, delete-orphan"
#     )

#     # Connected to Ride model to satisfy back_populates="rides"
#     rides = relationship(
#         "Ride", back_populates="car", cascade="all, delete-orphan"
#     )

#     @property
#     def plate_number(self) -> str | None:
#         """Exposes license_plate as plate_number for clean Pydantic schema mapping."""
#         return self.license_plate


from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base  # Adjust import path if necessary


class Car(Base):
    __tablename__ = "cars"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
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