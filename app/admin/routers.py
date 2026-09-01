from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone

from app import models, utils, oauth2
from app.database import get_db
from app.admin import schemas

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.post("/login")
def admin_login(payload: schemas.AdminLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email.strip()).first()
    if not user or not utils.verify(payload.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. Admin privileges required.")

    access_token = oauth2.create_access_token(data={"user_id": user.id, "is_admin": True})
    return {"access_token": access_token, "token_type": "bearer", "role": "admin"}

@router.get("/pending-nin", response_model=List[schemas.AdminUserView])
def get_pending_nins(db: Session = Depends(get_db), admin: models.User = Depends(oauth2.get_current_admin)):
    return db.query(models.User).filter(
        models.User.nin_verification_status == models.VerificationStatusEnum.pending
    ).all()

@router.post("/users/{user_id}/verify-nin", response_model=schemas.AdminUserView)
def approve_nin(user_id: int, db: Session = Depends(get_db), admin: models.User = Depends(oauth2.get_current_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    user.nin_verification_status = models.VerificationStatusEnum.verified
    user.nin_verified_at = datetime.now(timezone.utc)
    user.nin_verification_notes = None
    db.commit()
    db.refresh(user)
    return user

@router.post("/users/{user_id}/reject-nin", response_model=schemas.AdminUserView)
def reject_nin(user_id: int, action: schemas.VerificationAction, db: Session = Depends(get_db), admin: models.User = Depends(oauth2.get_current_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.nin_verification_status = models.VerificationStatusEnum.failed
    user.nin_verification_notes = action.notes
    db.commit()
    db.refresh(user)
    return user

@router.get("/pending-licenses", response_model=List[schemas.AdminDriverView])
def get_pending_licenses(db: Session = Depends(get_db), admin: models.User = Depends(oauth2.get_current_admin)):
    return db.query(models.DriverProfile).filter(
        models.DriverProfile.license_verification_status == models.VerificationStatusEnum.pending
    ).all()

@router.post("/drivers/{user_id}/verify-license", response_model=schemas.AdminDriverView)
def approve_license(user_id: int, db: Session = Depends(get_db), admin: models.User = Depends(oauth2.get_current_admin)):
    driver_profile = db.query(models.DriverProfile).filter(models.DriverProfile.user_id == user_id).first()
    if not driver_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver profile not found")

    driver_profile.license_verification_status = models.VerificationStatusEnum.verified
    driver_profile.license_verification_notes = None
    db.commit()
    db.refresh(driver_profile)
    return driver_profile