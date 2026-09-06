from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base # Assume Base is imported from central database config[cite: 1.2.2]

class AdminLog(Base):
    """
    Optional but recommended: Stores a record of actions taken by admins
    for auditing purposes (e.g., who verified which NIN)[cite: 1.1.1].
    """
    __tablename__ = "admin_logs"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("admins.id"), nullable=False)
    action = Column(String, nullable=False) # e.g., "VERIFY_NIN", "CREATE_ADMIN"
    target_id = Column(String, nullable=False) # ID of user/driver acted upon
    details = Column(String, nullable=True) # Optional notes
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    admin = relationship("Admin", back_populates="logs")


class Admin(Base):
    """
    Defines the specific table for administrative users[cite: 1.1.2, 1.3].
    """
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    
    # Hierarchy control[cite: 1.1.2, 1.3]
    is_active = Column(Boolean, server_default='True', nullable=False)
    is_super_admin = Column(Boolean, server_default='False', nullable=False) 
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    logs = relationship("AdminLog", back_populates="admin")