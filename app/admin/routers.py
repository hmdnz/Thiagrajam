# """
# app/admin/routers.py — DEDICATED ADMIN ROUTER
# """

# import os
# from uuid import UUID
# from fastapi import APIRouter, Depends, HTTPException, status, Header
# from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
# from sqlalchemy.orm import Session

# from app.database import get_db
# from app import models, utils, oauth2
# from app.schemas import VerificationStatusEnum
# from app.admin import models as admin_models, schemas as admin_schemas

# router = APIRouter(prefix="/admin", tags=["Admin Module"])

# oauth2_scheme_admin = OAuth2PasswordBearer(tokenUrl="admin/login")


# def get_current_admin_user(
#     token: str = Depends(oauth2_scheme_admin),
#     db: Session = Depends(get_db)
# ) -> admin_models.AdminUser:
#     """Dependency: Decodes token and verifies caller is an active AdminUser."""

#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate admin credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )

#     token_data = oauth2.verify_access_token(token, credentials_exception)

#     try:
#         admin_id = UUID(str(token_data))
#     except (ValueError, TypeError):
#         raise credentials_exception

#     admin = db.query(admin_models.AdminUser).filter(
#         admin_models.AdminUser.id == admin_id
#     ).first()

#     if not admin or not admin.is_active:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Inactive or unauthorized administrator account."
#         )

#     return admin



# def get_current_super_admin(
#     current_admin: admin_models.AdminUser = Depends(get_current_admin_user)
# ) -> admin_models.AdminUser:
#     """Dependency: Ensures the authenticated admin user has Super Admin privileges."""
#     if not (current_admin.is_superadmin or current_admin.role == admin_models.AdminRoleEnum.SUPER_ADMIN):
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
#     """Initial Setup Endpoint: Creates the initial Super Admin account."""
#     expected_secret = os.getenv("BOOTSTRAP_SECRET", "wenyfour_super_secret_bootstrap_key_2026")
    
#     if x_bootstrap_secret != expected_secret:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid bootstrap secret key."
#         )

#     existing_admin = db.query(admin_models.AdminUser).filter(
#         admin_models.AdminUser.email == admin_in.email
#     ).first()
#     if existing_admin:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Admin user with this email already exists."
#         )

#     hashed_pwd = utils.hash(admin_in.password)
    
#     new_superadmin = admin_models.AdminUser(
#         email=admin_in.email,
#         hashed_password=hashed_pwd,
#         full_name=admin_in.full_name,
#         role=admin_models.AdminRoleEnum.SUPER_ADMIN,
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
#     """Super Admin Endpoint: Creates targeted role accounts."""
#     existing_admin = db.query(admin_models.AdminUser).filter(
#         admin_models.AdminUser.email == admin_in.email
#     ).first()
#     if existing_admin:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Admin account with this email already exists."
#         )

#     hashed_pwd = utils.hash(admin_in.password)
#     is_super = (admin_in.role == admin_models.AdminRoleEnum.SUPER_ADMIN)

#     new_admin = admin_models.AdminUser(
#         email=admin_in.email,
#         hashed_password=hashed_pwd,
#         full_name=admin_in.full_name,
#         role=admin_in.role,
#         is_active=True,
#         is_superadmin=is_super
#     )

#     db.add(new_admin)

#     audit = admin_models.AdminAuditLog(
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


# # ============================================================
# # ADMIN AUTHENTICATION
# # POST /admin/login
# # ============================================================

# @router.post("/login", response_model=admin_schemas.AdminToken)
# def admin_login(
#     form_data: OAuth2PasswordRequestForm = Depends(),
#     db: Session = Depends(get_db)
# ):
#     """Authenticates an admin user and returns a Bearer token."""
#     # OAuth2PasswordRequestForm uses 'username' field for the email address
#     admin = db.query(admin_models.AdminUser).filter(
#         admin_models.AdminUser.email == form_data.username
#     ).first()
    
#     if not admin or not utils.verify(form_data.password, admin.hashed_password):
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,  # Use 401 for auth failures
#             detail="Invalid admin credentials",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
    
#     if not admin.is_active:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Admin account is inactive."
#         )

#     # Standardize payload payload to use 'sub' or include 'user_id'
#     access_token = oauth2.create_access_token(
#         data={"sub": str(admin.id), "user_id": str(admin.id), "is_admin": True}
#     )

#     # 🔍 PRINT TOKEN UPON LOGIN
#     print("\n" + "="*50)
#     print(f"[LOGIN SUCCESS] Admin ID: {admin.id}")
#     print(f"[LOGIN SUCCESS] Generated Token: {access_token}")
#     print("="*50 + "\n")


#     return {"access_token": access_token, "token_type": "bearer"}


# # ============================================================
# # NIN VERIFICATION
# # POST /admin/verify-nin/{user_id}
# # ============================================================

# @router.post("/verify-nin/{user_id}", response_model=dict)
# def approve_nin(
#     user_id: UUID,
#     payload: admin_schemas.VerificationActionPayload = admin_schemas.VerificationActionPayload(),
#     db: Session = Depends(get_db),
#     current_admin: admin_models.AdminUser = Depends(get_current_admin_user)
# ):
#     """Approves a passenger's NIN submission and records an audit log entry."""
#     user = db.query(models.User).filter(models.User.id == user_id).first()
#     if not user:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

#     user.nin_verification_status = VerificationStatusEnum.verified
#     user.nin_verified = True

#     audit = admin_models.AdminAuditLog(
#         admin_id=current_admin.id,
#         action="VERIFY_NIN",
#         target_entity="users",
#         target_id=str(user.id),
#         reason=payload.reason or "NIN document verified by admin."
#     )
#     db.add(audit)
#     db.commit()

#     return {"status": "success", "message": f"NIN verified for user {user.email}"}


# # ============================================================
# # DRIVER LICENSE VERIFICATION
# # POST /admin/verify-license/{user_id}
# # ============================================================

# @router.post("/verify-license/{user_id}", response_model=dict)
# def approve_license(
#     user_id: UUID,
#     payload: admin_schemas.VerificationActionPayload = admin_schemas.VerificationActionPayload(),
#     db: Session = Depends(get_db),
#     current_admin: admin_models.AdminUser = Depends(get_current_admin_user)
# ):
#     """Approves a driver's license submission and unlocks ride creation rights."""
#     user = db.query(models.User).filter(models.User.id == user_id).first()
#     if not user:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

#     if user.nin_verification_status != VerificationStatusEnum.verified:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Cannot verify driver's license before NIN is verified."
#         )

#     driver_profile = user.driver_profile
#     if not driver_profile:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver profile not found")

#     driver_profile.license_verification_status = VerificationStatusEnum.verified
#     user.can_offer_rides = True

#     audit = admin_models.AdminAuditLog(
#         admin_id=current_admin.id,
#         action="APPROVE_LICENSE",
#         target_entity="drivers",
#         target_id=str(driver_profile.id),
#         reason=payload.reason or "Driver license verified by admin."
#     )
#     db.add(audit)
#     db.commit()

#     return {"status": "success", "message": f"Driver license approved for {user.email}."}


# # ============================================================
# # PENDING VERIFICATIONS QUEUE
# # GET /admin/pending-drivers
# # ============================================================

# @router.get("/pending-drivers", response_model=list)
# def get_pending_drivers(
#     db: Session = Depends(get_db),
#     current_admin: admin_models.AdminUser = Depends(get_current_admin_user)
# ):
#     """Retrieves all users with pending NIN or License verification."""
#     pending_users = db.query(models.User).filter(
#         (models.User.nin_verification_status == VerificationStatusEnum.pending) |
#         (models.User.can_offer_rides == False)
#     ).all()
    
#     return [
#         {
#             "user_id": str(u.id),
#             "email": u.email,
#             "nin_status": u.nin_verification_status,
#             "can_offer_rides": u.can_offer_rides,
#             "has_driver_profile": u.driver_profile is not None
#         }
#         for u in pending_users
#     ]

"""
app/admin/routers.py
Dedicated Admin Router

Provides:
- Admin OAuth2 password login
- Swagger OAuth2 authorization for admin endpoints
- Super-admin authorization
- Admin account creation
- NIN verification
- Driver license verification
- Pending verification queue
"""

import os
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Header,
    status,
)
from fastapi.security import (
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
)
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, utils, oauth2
from app.schemas import VerificationStatusEnum
from app.admin import models as admin_models
from app.admin import schemas as admin_schemas


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/admin",
    tags=["Admin Module"],
)


# ============================================================
# ADMIN OAUTH2 SECURITY SCHEME
# ============================================================
#
# This is what tells Swagger:
#
#   AdminAuth
#   OAuth2, password
#   Token URL: /admin/login
#
# The login endpoint uses OAuth2PasswordRequestForm, so Swagger
# can send:
#
#   username = admin email
#   password = admin password
#
# ============================================================

oauth2_scheme_admin = OAuth2PasswordBearer(
    tokenUrl="/admin/login",
)


# ============================================================
# GET CURRENT ADMIN
# ============================================================

def get_current_admin_user(
    token: str = Depends(oauth2_scheme_admin),
    db: Session = Depends(get_db),
) -> admin_models.AdminUser:
    """
    Dependency that:
    1. Extracts the Bearer token.
    2. Verifies the JWT.
    3. Gets the admin UUID from the token.
    4. Loads the AdminUser from the database.
    5. Ensures the admin account is active.
    """

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate admin credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # --------------------------------------------------------
    # Verify JWT
    # --------------------------------------------------------

    token_data = oauth2.verify_access_token(
        token,
        credentials_exception,
    )

    # Your current verify_access_token() returns the "sub"
    # value as a string.
    #
    # Example:
    #
    # "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    #
    # Therefore, DO NOT do:
    #
    # token_data.id
    #
    # because token_data is a string.

    try:
        admin_id = UUID(str(token_data))
    except (ValueError, TypeError):
        raise credentials_exception

    # --------------------------------------------------------
    # Find admin in database
    # --------------------------------------------------------

    admin = (
        db.query(admin_models.AdminUser)
        .filter(admin_models.AdminUser.id == admin_id)
        .first()
    )

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin account not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # --------------------------------------------------------
    # Check account status
    # --------------------------------------------------------

    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive or unauthorized administrator account.",
        )

    return admin


# ============================================================
# GET CURRENT SUPER ADMIN
# ============================================================

def get_current_super_admin(
    current_admin: admin_models.AdminUser = Depends(
        get_current_admin_user
    ),
) -> admin_models.AdminUser:
    """
    Ensures the currently authenticated admin is a Super Admin.
    """

    is_super_admin = (
        current_admin.is_superadmin
        or current_admin.role == admin_models.AdminRoleEnum.SUPER_ADMIN
    )

    if not is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin privileges required to perform this action.",
        )

    return current_admin


# ============================================================
# INITIAL BOOTSTRAP
# POST /admin/bootstrap-superadmin
# ============================================================

@router.post(
    "/bootstrap-superadmin",
    response_model=admin_schemas.AdminOut,
    status_code=status.HTTP_201_CREATED,
)
def bootstrap_superadmin(
    admin_in: admin_schemas.AdminCreate,
    x_bootstrap_secret: str = Header(
        ...,
        description="Secret key passed in headers for initial setup",
    ),
    db: Session = Depends(get_db),
):
    """
    Creates the initial Super Admin account.

    This endpoint is protected by BOOTSTRAP_SECRET.
    """

    expected_secret = os.getenv(
        "BOOTSTRAP_SECRET",
        "wenyfour_super_secret_bootstrap_key_2026",
    )

    if x_bootstrap_secret != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bootstrap secret key.",
        )

    # --------------------------------------------------------
    # Check whether email already exists
    # --------------------------------------------------------

    existing_admin = (
        db.query(admin_models.AdminUser)
        .filter(admin_models.AdminUser.email == admin_in.email)
        .first()
    )

    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin user with this email already exists.",
        )

    # --------------------------------------------------------
    # Hash password
    # --------------------------------------------------------

    hashed_pwd = utils.hash(admin_in.password)

    # --------------------------------------------------------
    # Create Super Admin
    # --------------------------------------------------------

    new_superadmin = admin_models.AdminUser(
        email=admin_in.email,
        hashed_password=hashed_pwd,
        full_name=admin_in.full_name,
        role=admin_models.AdminRoleEnum.SUPER_ADMIN,
        is_active=True,
        is_superadmin=True,
    )

    db.add(new_superadmin)
    db.commit()
    db.refresh(new_superadmin)

    return new_superadmin


# ============================================================
# SUPER ADMIN
# CREATE OTHER ADMIN ACCOUNTS
#
# POST /admin/create-admin
# ============================================================

@router.post(
    "/create-admin",
    response_model=admin_schemas.AdminOut,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_user(
    admin_in: admin_schemas.AdminCreate,
    db: Session = Depends(get_db),
    current_super_admin: admin_models.AdminUser = Depends(
        get_current_super_admin
    ),
):
    """
    Creates another administrator account.

    Only Super Admins can access this endpoint.
    """

    # --------------------------------------------------------
    # Check duplicate email
    # --------------------------------------------------------

    existing_admin = (
        db.query(admin_models.AdminUser)
        .filter(admin_models.AdminUser.email == admin_in.email)
        .first()
    )

    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin account with this email already exists.",
        )

    # --------------------------------------------------------
    # Hash password
    # --------------------------------------------------------

    hashed_pwd = utils.hash(admin_in.password)

    is_super = (
        admin_in.role == admin_models.AdminRoleEnum.SUPER_ADMIN
    )

    # --------------------------------------------------------
    # Create admin
    # --------------------------------------------------------

    new_admin = admin_models.AdminUser(
        email=admin_in.email,
        hashed_password=hashed_pwd,
        full_name=admin_in.full_name,
        role=admin_in.role,
        is_active=True,
        is_superadmin=is_super,
    )

    db.add(new_admin)

    # --------------------------------------------------------
    # Audit log
    # --------------------------------------------------------

    audit = admin_models.AdminAuditLog(
        admin_id=current_super_admin.id,
        action="CREATE_ADMIN_ACCOUNT",
        target_entity="admin_users",
        target_id=str(new_admin.id),
        reason=(
            f"Created {admin_in.role.value} account "
            f"for {admin_in.email}."
        ),
    )

    db.add(audit)

    db.commit()
    db.refresh(new_admin)

    return new_admin


# ============================================================
# ADMIN LOGIN
# POST /admin/login
# ============================================================

@router.post(
    "/login",
    response_model=admin_schemas.AdminToken,
)
def admin_login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Admin OAuth2 password login.

    Swagger will send:

        username = admin email
        password = admin password

    The username field is intentionally used for the
    administrator's email address.
    """

    # --------------------------------------------------------
    # Find admin by email
    # --------------------------------------------------------

    admin = (
        db.query(admin_models.AdminUser)
        .filter(
            admin_models.AdminUser.email == form_data.username
        )
        .first()
    )

    # --------------------------------------------------------
    # Validate credentials
    # --------------------------------------------------------

    if not admin or not utils.verify(
        form_data.password,
        admin.hashed_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # --------------------------------------------------------
    # Check account status
    # --------------------------------------------------------

    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is inactive.",
        )

    # --------------------------------------------------------
    # Generate JWT
    # --------------------------------------------------------
    #
    # "sub" is the important claim.
    #
    # Your verify_access_token() currently returns this
    # value as a string.
    #
    # --------------------------------------------------------

    access_token = oauth2.create_access_token(
        data={
            "sub": str(admin.id),
            "user_id": str(admin.id),
            "is_admin": True,
        }
    )

    # --------------------------------------------------------
    # Debug logging
    # --------------------------------------------------------
    #
    # Do NOT print the actual token in production.
    # --------------------------------------------------------

    print("\n" + "=" * 50)
    print(f"[ADMIN LOGIN SUCCESS] Admin ID: {admin.id}")
    print("[ADMIN LOGIN SUCCESS] Access token generated")
    print("=" * 50 + "\n")

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


# ============================================================
# VERIFY NIN
#
# POST /admin/verify-nin/{user_id}
# ============================================================

@router.post(
    "/verify-nin/{user_id}",
    response_model=dict,
)
def approve_nin(
    user_id: UUID,
    payload: admin_schemas.VerificationActionPayload = Depends(),
    db: Session = Depends(get_db),
    current_admin: admin_models.AdminUser = Depends(
        get_current_admin_user
    ),
):
    """
    Approves a passenger's NIN submission.
    """

    # --------------------------------------------------------
    # Find user
    # --------------------------------------------------------

    user = (
        db.query(models.User)
        .filter(models.User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # --------------------------------------------------------
    # Update verification status
    # --------------------------------------------------------

    user.nin_verification_status = (
        VerificationStatusEnum.verified
    )

    user.nin_verified = True

    # --------------------------------------------------------
    # Audit log
    # --------------------------------------------------------

    audit = admin_models.AdminAuditLog(
        admin_id=current_admin.id,
        action="VERIFY_NIN",
        target_entity="users",
        target_id=str(user.id),
        reason=(
            payload.reason
            or "NIN document verified by admin."
        ),
    )

    db.add(audit)

    db.commit()

    return {
        "status": "success",
        "message": f"NIN verified for user {user.email}",
    }


# ============================================================
# VERIFY DRIVER LICENSE
#
# POST /admin/verify-license/{user_id}
# ============================================================

@router.post(
    "/verify-license/{user_id}",
    response_model=dict,
)
def approve_license(
    user_id: UUID,
    payload: admin_schemas.VerificationActionPayload = Depends(),
    db: Session = Depends(get_db),
    current_admin: admin_models.AdminUser = Depends(
        get_current_admin_user
    ),
):
    """
    Approves a driver's license.

    NIN must already be verified.
    """

    # --------------------------------------------------------
    # Find user
    # --------------------------------------------------------

    user = (
        db.query(models.User)
        .filter(models.User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # --------------------------------------------------------
    # NIN must be verified first
    # --------------------------------------------------------

    if (
        user.nin_verification_status
        != VerificationStatusEnum.verified
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Cannot verify driver's license "
                "before NIN is verified."
            ),
        )

    # --------------------------------------------------------
    # Get driver profile
    # --------------------------------------------------------

    driver_profile = user.driver_profile

    if not driver_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver profile not found",
        )

    # --------------------------------------------------------
    # Approve license
    # --------------------------------------------------------

    driver_profile.license_verification_status = (
        VerificationStatusEnum.verified
    )

    user.can_offer_rides = True

    # --------------------------------------------------------
    # Audit log
    # --------------------------------------------------------

    audit = admin_models.AdminAuditLog(
        admin_id=current_admin.id,
        action="APPROVE_LICENSE",
        target_entity="drivers",
        target_id=str(driver_profile.id),
        reason=(
            payload.reason
            or "Driver license verified by admin."
        ),
    )

    db.add(audit)

    db.commit()

    return {
        "status": "success",
        "message": (
            f"Driver license approved for {user.email}."
        ),
    }


# ============================================================
# PENDING VERIFICATIONS
#
# GET /admin/pending-drivers
# ============================================================

@router.get(
    "/pending-drivers",
    response_model=list,
)
def get_pending_drivers(
    db: Session = Depends(get_db),
    current_admin: admin_models.AdminUser = Depends(
        get_current_admin_user
    ),
):
    """
    Retrieves users with pending NIN or driver verification.
    """

    pending_users = (
        db.query(models.User)
        .filter(
            (models.User.nin_verification_status == VerificationStatusEnum.pending)
            | (models.User.can_offer_rides == False)
        )
        .all()
    )

    return [
        {
            "user_id": str(user.id),
            "email": user.email,
            "nin_status": user.nin_verification_status,
            "can_offer_rides": user.can_offer_rides,
            "has_driver_profile": (
                user.driver_profile is not None
            ),
        }
        for user in pending_users
    ]
