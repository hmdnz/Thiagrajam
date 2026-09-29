"""
app/admin/models.py — DEDICATED ADMIN MODELS

Defines administrative accounts, permission roles, and audit logging.
"""

import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum as SQLEnum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Session
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi import status


from app.database import Base
from app.database import get_db

router = APIRouter()


class AdminRoleEnum(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    VERIFICATION_OFFICER = "VERIFICATION_OFFICER"
    DISPUTE_MANAGER = "DISPUTE_MANAGER"
    SUPPORT_AGENT = "SUPPORT_AGENT"


class AdminUser(Base):
    """
    Dedicated table for platform administrators. Keeps administrative identities
    isolated from regular passenger/driver user records.
    """
    __tablename__ = "admin_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    
    role = Column(
        SQLEnum(AdminRoleEnum, name="admin_role_enum"), 
        default=AdminRoleEnum.VERIFICATION_OFFICER, 
        nullable=False
    )
    is_active = Column(Boolean, default=True, nullable=False)
    is_superadmin = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc), 
        nullable=False
    )

    # Relationships
    audit_logs = relationship("AdminAuditLog", back_populates="admin")


class AdminAuditLog(Base):
    """
    Tracks administrative actions (KYC approvals, rejections, dispute holds)
    for compliance and auditability.
    """
    __tablename__ = "admin_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    admin_id = Column(UUID(as_uuid=True), ForeignKey("admin_users.id"), nullable=False)
    
    action = Column(String, nullable=False)       # e.g., "VERIFY_NIN", "APPROVE_LICENSE", "FREEZE_ESCROW"
    target_entity = Column(String, nullable=False)  # e.g., "users", "drivers", "bookings"
    target_id = Column(String, nullable=False)      # UUID or string representation of target entity ID
    reason = Column(Text, nullable=True)          # Optional explanation or justification
    
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    admin = relationship("AdminUser", back_populates="audit_logs")

# def get_current_super_admin(
#     current_admin: AdminUser = Depends(get_current_admin)
# ) -> AdminUser:
#     """
#     Dependency: Ensures the authenticated admin user has Super Admin privileges.
#     """
#     if not (current_admin.is_superadmin or current_admin.role == AdminRoleEnum.SUPER_ADMIN):
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Super Admin privileges required to perform this action."
#         )
#     return current_admin


# # ============================================================
# # INITIAL BOOTSTRAP: CREATE FIRST SUPER ADMIN
# # POST /admin/bootstrap-superadmin
# # ============================================================

# @router.post(
#     "/bootstrap-superadmin",
#     response_model=admin_schemas.AdminOut,
#     status_code=status.HTTP_201_CREATED
# )
# def bootstrap_superadmin(
#     admin_in: admin_schemas.AdminCreate,
#     x_bootstrap_secret: str = Header(..., description="Secret key passed in headers for initial setup"),
#     db: Session = Depends(get_db)
# ):
#     """
#     Initial Setup Endpoint: Allows creating the first Super Admin account.
#     Protected via a system environment variable or secret header (`BOOTSTRAP_SECRET`).
#     """
#     expected_secret = os.getenv("BOOTSTRAP_SECRET", "wenyfour_super_secret_bootstrap_key_2026")
    
#     if x_bootstrap_secret != expected_secret:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid bootstrap secret key."
#         )

#     # Check if email already exists
#     existing_admin = db.query(AdminUser).filter(
#         AdminUser.email == admin_in.email
#     ).first()
#     if existing_admin:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Admin user with this email already exists."
#         )

#     hashed_pwd = utils.hash(admin_in.password)
    
#     new_superadmin = AdminUser(
#         email=admin_in.email,
#         hashed_password=hashed_pwd,
#         full_name=admin_in.full_name,
#         role=AdminRoleEnum.SUPER_ADMIN,
#         is_active=True,
#         is_superadmin=True
#     )

#     db.add(new_superadmin)
#     db.commit()
#     db.refresh(new_superadmin)

#     return new_superadmin


# # ============================================================
# # SUPER ADMIN: CREATE OTHER ADMINS / OFFICERS / AGENTS
# # POST /admin/create-admin
# # ============================================================

# @router.post(
#     "/create-admin",
#     response_model=admin_schemas.AdminOut,
#     status_code=status.HTTP_201_CREATED
# )
# def create_admin_user(
#     admin_in: admin_schemas.AdminCreate,
#     db: Session = Depends(get_db),
#     current_super_admin: admin_models.AdminUser = Depends(get_current_super_admin)
# ):
#     """
#     Super Admin Endpoint: Allows a Super Admin to create:
#       - SUPER_ADMIN
#       - VERIFICATION_OFFICER
#       - DISPUTE_MANAGER
#       - SUPPORT_AGENT
#     """
#     # Check if user already exists
#     existing_admin = db.query(AdminUser).filter(
#         AdminUser.email == admin_in.email
#     ).first()
#     if existing_admin:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Admin account with this email already exists."
#         )

#     hashed_pwd = utils.hash(admin_in.password)

#     # If the role is SUPER_ADMIN, mark is_superadmin=True
#     is_super = (admin_in.role == AdminRoleEnum.SUPER_ADMIN)

#     new_admin = AdminUser(
#         email=admin_in.email,
#         hashed_password=hashed_pwd,
#         full_name=admin_in.full_name,
#         role=admin_in.role,
#         is_active=True,
#         is_superadmin=is_super
#     )

#     db.add(new_admin)

#     # Log audit entry
#     audit = AdminAuditLog(
#         admin_id=current_super_admin.id,
#         action="CREATE_ADMIN_ACCOUNT",
#         target_entity="admin_users",
#         target_id=str(new_admin.id),
#         reason=f"Created {admin_in.role.value} account for {admin_in.email}."
#     )
#     db.add(audit)

#     db.commit()
#     db.refresh(new_admin)

#     return new_admin
