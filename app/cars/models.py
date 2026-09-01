from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, text
from sqlalchemy.orm import relationship
from app.database import Base

class Car(Base):
    __tablename__ = "cars"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    make = Column(String, nullable=False)
    model = Column(String, nullable=False)
    year = Column(Integer, nullable=False)
    color = Column(String, nullable=False)
    plate_number = Column(String, unique=True, nullable=False, index=True)
    capacity = Column(Integer, nullable=False, default=4)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

    driver = relationship("User")