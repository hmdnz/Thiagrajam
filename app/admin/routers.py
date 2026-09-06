from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone

from app import models, utils, oauth2 # Existing core imports maintained[cite: 1.2.1]
from app.database import get_db

from app import database, oauth2
from app.admin import models as admin_models

# CRITICAL: We now import the newly defined Admin Model[cite: 1.1.2]
from app.admin import models as admin_models 
from app.admin import schemas

router = APIRouter(prefix="/admin", tags=["Admin"])

# =========================================================================
# 🚀 Super Admin Routes (Hierarchy Control) [cite: 1.3, 1.4]
# =========================================================================
# Rule: Super Admin can manage Admins[cite: 1.1.2]. 
# Authenticated by get_current_super_admin[cite: 1.3.1].
# =========================================================================

@router.get("/", response_model=List[schemas.AdminOut])
def get_all_admins(
    db: Session = Depends(database.get_db),
    # RESTRICTED: Only logged-in Super Admins can list all administrators
    current_super_admin: admin_models.Admin = Depends(oauth2.get_current_super_admin)
):
    """
    Retrieve all registered administrator accounts.
    Accessible exclusively by Super Admins.
    """
    admins = db.query(admin_models.Admin).all()
    return admins


@router.post("/admins", response_model=schemas.AdminOut, status_code=status.HTTP_201_CREATED)
def create_new_admin(
    payload: schemas.AdminCreate, 
    db: Session = Depends(get_db), 
    # STRICT Dependency: Only Super Admins allowed[cite: 1.3.1]
    current_super_admin: admin_models.Admin = Depends(oauth2.get_current_super_admin) 
):
    """
    A Super Admin creates a regular Admin account[cite: 1.1.2, 1.4].
    """
    # 1. Check if email already registered in the admins table
    existing_admin = db.query(admin_models.Admin).filter(
        admin_models.Admin.email == payload.email.strip()
    ).first()
    
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Admin with this email already exists."
        )

    # 2. Hash password (utils assumed from your imports)[cite: 1.2.1]
    hashed_password = utils.hash(payload.password)

    # 3. Create Admin object, strictly setting is_super_admin=False[cite: 1.1.2, 1.3]
    new_admin = admin_models.Admin(
        **payload.dict(exclude={'password'}),
        hashed_password=hashed_password,
        is_super_admin=False # Ensure regular admin status[cite: 1.1.2]
    )
    
    # 4. Save and return view[cite: 1.1.2]
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    return new_admin


# =========================================================================
# 🛠️ Standard Admin Routes (Verification Logic) [cite: 1.3.1, 1.4]
# =========================================================================
# Authenticated by get_current_admin[cite: 1.3.1] (Admins and Super Admins allowed).
# =========================================================================

@router.post("/login", response_model=schemas.Token)
def admin_login(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(database.get_db)
):
    """
    Authenticates Admin users and returns an OAuth2 bearer token.
    Swagger UI reads username (email) and password from form-data.
    """
    # 1. Look up admin by email (form_data.username contains the email)
    admin = db.query(admin_models.Admin).filter(
        admin_models.Admin.email == form_data.username.strip()
    ).first()

    # 2. Validate existence and password
    if not admin or not utils.verify(form_data.password, admin.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is inactive."
        )

    # 3. Create token with admin_id payload
    access_token = oauth2.create_access_token(data={"admin_id": admin.id})

    # 4. Return token object matching schemas.Token
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/pending-nin", response_model=List[schemas.AdminUserView])
def get_pending_nins(db: Session = Depends(get_db), admin: admin_models.Admin = Depends(oauth2.get_current_admin)):
    # Update type hint to admin_models.Admin[cite: 1.1.2]
    return db.query(models.User).filter(
        models.User.nin_verification_status == models.VerificationStatusEnum.pending
    ).all()

@router.post("/users/{user_id}/verify-nin", response_model=schemas.AdminUserView)
def approve_nin(user_id: int, db: Session = Depends(get_db), admin: admin_models.Admin = Depends(oauth2.get_current_admin)):
    # ... your existing verify-nin logic ...
    pass

@router.post("/users/{user_id}/reject-nin", response_model=schemas.AdminUserView)
def reject_nin(user_id: int, action: schemas.VerificationAction, db: Session = Depends(get_db), admin: admin_models.Admin = Depends(oauth2.get_current_admin)):
    # ... your existing reject-nin logic ...
    pass

@router.get("/pending-licenses", response_model=List[schemas.AdminDriverView])
def get_pending_licenses(db: Session = Depends(get_db), admin: admin_models.Admin = Depends(oauth2.get_current_admin)):
    return db.query(models.DriverProfile).filter(
        models.DriverProfile.license_verification_status == models.VerificationStatusEnum.pending
    ).all()

@router.post("/drivers/{user_id}/verify-license", response_model=schemas.AdminDriverView)
def approve_license(user_id: int, db: Session = Depends(get_db), admin: admin_models.Admin = Depends(oauth2.get_current_admin)):
    # ... your existing verify-license logic ...
    pass

