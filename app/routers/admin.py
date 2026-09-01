# from datetime import datetime, timezone
# from typing import List
# from fastapi import APIRouter, Depends, HTTPException, status
# from sqlalchemy.orm import Session

# from .. import models, schemas, oauth2
# from ..database import get_db

# # All routes here require an admin account — every route uses
# # oauth2.get_current_admin instead of get_current_user, so a non-admin
# # gets a 403 before the route body even runs.
# router = APIRouter(prefix="/admin", tags=["Admin"])


# # ---------------------------------------------------------------
# # NIN / identity verification
# # ---------------------------------------------------------------

# @router.get("/users/pending-nin", response_model=List[schemas.UserProfileOut])
# def list_pending_nin(
#     db: Session = Depends(get_db),
#     admin: models.User = Depends(oauth2.get_current_admin),
# ):
#     """Lists every user whose NIN + selfie are submitted and waiting
#     on manual admin review."""
#     return db.query(models.User).filter(
#         models.User.nin_verification_status == models.VerificationStatusEnum.pending
#     ).all()


# @router.post("/users/{user_id}/nin/approve", response_model=schemas.UserProfileOut)
# def approve_nin(
#     user_id: int,
#     db: Session = Depends(get_db),
#     admin: models.User = Depends(oauth2.get_current_admin),
# ):
#     """Marks a user's NIN as verified. Requires both a NIN and a selfie
#     to actually be present — an admin shouldn't be able to approve
#     identity verification with nothing to check it against."""
#     user = db.query(models.User).filter(models.User.id == user_id).first()
#     if not user:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

#     if not user.nin or not user.photo_url:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="User has not submitted both a NIN and a selfie yet.",
#         )

#     user.nin_verification_status = models.VerificationStatusEnum.verified
#     user.nin_verified_at = datetime.now(timezone.utc)
#     user.nin_verification_notes = None  # clear any old rejection note

#     db.commit()
#     db.refresh(user)
#     return user


# @router.post("/users/{user_id}/nin/reject", response_model=schemas.UserProfileOut)
# def reject_nin(
#     user_id: int,
#     payload: schemas.AdminRejection,
#     db: Session = Depends(get_db),
#     admin: models.User = Depends(oauth2.get_current_admin),
# ):
#     """Marks a user's NIN check as failed and records why, so the
#     user sees the reason and can correct/resubmit."""
#     user = db.query(models.User).filter(models.User.id == user_id).first()
#     if not user:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

#     user.nin_verification_status = models.VerificationStatusEnum.failed
#     user.nin_verification_notes = payload.reason
#     user.nin_verified_at = None  # never was actually verified, so clear this

#     db.commit()
#     db.refresh(user)
#     return user


# # ---------------------------------------------------------------
# # Driving licence verification
# # ---------------------------------------------------------------

# @router.get("/drivers/pending-license", response_model=List[schemas.DriverProfileOut])
# def list_pending_licenses(
#     db: Session = Depends(get_db),
#     admin: models.User = Depends(oauth2.get_current_admin),
# ):
#     """Lists every DriverProfile waiting on manual licence/vehicle
#     document review."""
#     return db.query(models.DriverProfile).filter(
#         models.DriverProfile.license_verification_status == models.VerificationStatusEnum.pending
#     ).all()


# @router.post("/drivers/{user_id}/license/approve", response_model=schemas.DriverProfileOut)
# def approve_license(
#     user_id: int,
#     db: Session = Depends(get_db),
#     admin: models.User = Depends(oauth2.get_current_admin),
# ):
#     """Marks a driver's licence as verified. Requires the licence
#     number, photo, and expiry date all be present first."""
#     driver_profile = db.query(models.DriverProfile).filter(
#         models.DriverProfile.user_id == user_id
#     ).first()
#     if not driver_profile:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver profile not found.")

#     if not driver_profile.is_complete():
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Driver has not submitted licence number, photo, and expiry date yet.",
#         )

#     driver_profile.license_verification_status = models.VerificationStatusEnum.verified
#     driver_profile.license_verification_notes = None

#     db.commit()
#     db.refresh(driver_profile)
#     return driver_profile


# @router.post("/drivers/{user_id}/license/reject", response_model=schemas.DriverProfileOut)
# def reject_license(
#     user_id: int,
#     payload: schemas.AdminRejection,
#     db: Session = Depends(get_db),
#     admin: models.User = Depends(oauth2.get_current_admin),
# ):
#     """Marks a driver's licence check as failed and records why."""
#     driver_profile = db.query(models.DriverProfile).filter(
#         models.DriverProfile.user_id == user_id
#     ).first()
#     if not driver_profile:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver profile not found.")

#     driver_profile.license_verification_status = models.VerificationStatusEnum.failed
#     driver_profile.license_verification_notes = payload.reason

#     db.commit()
#     db.refresh(driver_profile)
#     return driver_profile