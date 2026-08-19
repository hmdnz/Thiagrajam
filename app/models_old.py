from .database import Base
# from sqlalchemy import Column, Integer, String, Boolean,TEXT, TIMESTAMP, text

    # app/models.py

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, TIMESTAMP, Date, text
from sqlalchemy.orm import relationship
# from .database import Base

# class Post(Base): 
#     __tablename__ = "posts"

#     id = Column(Integer, primary_key=True, index=True)
#     title = Column(String, nullable=False)
#     content = Column(String, nullable=False)
#     published = Column(Boolean, server_default="true", nullable=False)
#     rating = Column(Integer, nullable=True)
#     created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))

# class User(Base):
#     __tablename__ = "users"

#     id = Column(Integer, primary_key=True, index=True)
#     email = Column(String, unique=True, nullable=True, index=True)
#     phone_number = Column(String, unique=True, nullable=True, index=True)
#     password = Column(String, nullable=False)  # Store a hashed password, not plain text
#     created_at = Column(
#         TIMESTAMP(timezone=True), nullable=False,server_default=text("now()")
#     )

# class User(Base):
#     __tablename__ = "users"

#     id           = Column(Integer, primary_key=True, index=True)
#     email        = Column(String, unique=True, nullable=True, index=True)
#     phone_number = Column(String, unique=True, nullable=True, index=True)
#     password     = Column(String, nullable=False)
#     is_active    = Column(Boolean, server_default="false", nullable=False)
#     created_at   = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

#     profile        = relationship("UserProfile", back_populates="user", uselist=False)
#     driver_profile = relationship("DriverProfile", back_populates="user", uselist=False)


# class UserProfile(Base):
#     __tablename__ = "user_profiles"

#     id                = Column(Integer, primary_key=True, index=True)
#     user_id           = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

#     # Editable fields
#     full_name         = Column(String, nullable=False)
#     address           = Column(String, nullable=False)
#     phone_number      = Column(String, nullable=False)
#     emergency_contact = Column(String, nullable=False)
#     photo_url         = Column(String, nullable=True)

#     # Fixed fields — set once, never updated
#     nin               = Column(String, unique=True, nullable=False)
#     date_of_birth     = Column(Date, nullable=False)  # stored as a date, age is calculated from it

#     created_at        = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
#     updated_at        = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))

#     user = relationship("User", back_populates="profile")


# class DriverProfile(Base):
#     __tablename__ = "driver_profiles"

#     id                = Column(Integer, primary_key=True, index=True)
#     user_id           = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

#     # Fixed — set once, never changed
#     licence_number    = Column(String, unique=True, nullable=False)
#     licence_photo_url = Column(String, nullable=False)

#     created_at        = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

#     user = relationship("User", back_populates="driver_profile")

class User(Base):
    __tablename__ = "users"

    id           = Column(Integer, primary_key=True, index=True)
    email        = Column(String, unique=True, nullable=True, index=True)
    phone_number = Column(String, unique=True, nullable=True, index=True)
    password     = Column(String, nullable=False)
    is_active    = Column(Boolean, server_default="false", nullable=False)

    # A user can be a passenger, a driver, or both — not mutually exclusive
    is_passenger = Column(Boolean, server_default="true", nullable=False)
    is_driver    = Column(Boolean, server_default="false", nullable=False)

    # ---- Profile fields ----
    # Not required at registration — filled in via a separate
    # "complete your profile" step, so all nullable here.
    full_name         = Column(String, nullable=True)
    address           = Column(String, nullable=True)
    emergency_contact = Column(String, nullable=True)
    photo_url         = Column(String, nullable=True)
    nin               = Column(String, unique=True, nullable=True)
    date_of_birth     = Column(Date, nullable=True)

    # ---- Driver-only fields ----
    # Only required once is_driver is set to True (via a
    # "become a driver" step). Nullable at the DB level.
    licence_number    = Column(String, unique=True, nullable=True)
    licence_photo_url = Column(String, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(
        TIMESTAMP(timezone=True), nullable=False,
        server_default=text("now()"), onupdate=text("now()"),
    )