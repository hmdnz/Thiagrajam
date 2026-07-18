from .database import Base
from sqlalchemy import Column, Integer, String, Boolean,TEXT, TIMESTAMP, text


class Post(Base): 
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    published = Column(Boolean, server_default="true", nullable=False)
    rating = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=True, index=True)
    phone_number = Column(String, unique=True, nullable=True, index=True)
    password = Column(String, nullable=False)  # Store a hashed password, not plain text
    created_at = Column(
        TIMESTAMP(timezone=True), nullable=False,server_default=text("now()")
    )