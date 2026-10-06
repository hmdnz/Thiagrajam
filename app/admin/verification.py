"""
app/admin/verification.py

Admin verification queue and decisions.

GET   /admin/verifications/summary
GET   /admin/verifications/pending-users      (NINs awaiting approval)
GET   /admin/verifications/pending-drivers    (licences awaiting approval)
PATCH /admin/verifications/users/{user_id}/nin
PATCH /admin/verifications/drivers/{user_id}/license

The decision body takes one of the VerificationStatusEnum values:
unverified | pending | verified | rejected.

Side effects on the gating flags:
  NIN verified     -> users.nin_verified = True,  users.can_book_rides = True
  NIN not verified -> users.nin_verified = False, users.can_book_rides = False,
                      users.can_offer_rides = False (a driver needs a verified NIN)
  Licence verified -> users.can_offer_rides = True, users.is_driver = True
  Licence not verified -> users.can_offer_rides = False

Suspension is separate (see app/admin/suspensions.py) and is checked
in addition to these flags, so verifying someone never lifts a suspension.
"""

from datetime import date
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app import models
from app.admin import models as admin_models
from app.admin import schemas as admin_schemas
from app.admin.permissions import VERIFICATION_ROLES, require_roles
from app.database import get_db

VS = models.VerificationStatusEnum

router = APIRouter(
    prefix="/admin/verifications",
    tags=["Admin - Verifications"],
)


# ------------------------------------------------------------
# helpers
# ------------------------------------------------------------

def _presign(key):
    """Short-lived URL for a private S3 object; None if missing/unavailable."""
    if not key:
        return None
    try:
        from app.s3_service import generate_presigned_url
        return generate_presigned_url(key, expires_in=900)
    except Exception:
        return None


def _license_expired(profile: models.DriverProfile) -> bool:
    return bool(
        profile.license_expiry_date
        and profile.license_expiry_date < date.today()
    )


def _audit(db, admin, action, entity, target_id, reason):
    db.add(
        admin_models.AdminAuditLog(
            admin_id=admin.id,
            action=action,
            target_entity=entity,
            target_id=str(target_id),
            reason=reason,
        )
    )


# ------------------------------------------------------------
# queue
# ------------------------------------------------------------

@router.get("/summary", response_model=admin_schemas.PendingSummaryOut)
def pending_summary(
    db: Session = Depends(get_db),
    _admin=Depends(require_roles(*VERIFICATION_ROLES)),
):
    """Counts for an admin dashboard badge."""
    return {
        "pending_nin_count": db.query(models.User)
        .filter(models.User.nin_verification_status == VS.pending)
        .count(),
        "pending_license_count": db.query(models.DriverProfile)
        .filter(models.DriverProfile.license_verification_status == VS.pending)
        .count(),
    }


@router.get("/pending-users", response_model=List[admin_schemas.PendingUserOut])
def list_pending_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _admin=Depends(require_roles(*VERIFICATION_ROLES)),
):
    """Users whose NIN + photo are submitted and waiting for review
    (oldest first)."""
    users = (
        db.query(models.User)
        .filter(models.User.nin_verification_status == VS.pending)
        .order_by(models.User.updated_at.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        admin_schemas.PendingUserOut(
            user_id=u.id,
            full_name=u.full_name,
            email=u.email,
            phone_number=u.phone_number,
            nin=u.nin,
            photo_url=_presign(u.photo_url),
            nin_verification_status=u.nin_verification_status,
            nin_verification_notes=u.nin_verification_notes,
            can_book_rides=u.can_book_rides,
            is_suspended=u.is_suspended,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.get(
    "/pending-drivers", response_model=List[admin_schemas.PendingDriverOut]
)
def list_pending_drivers(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _admin=Depends(require_roles(*VERIFICATION_ROLES)),
):
    """Driver profiles whose licence is waiting for review (oldest first)."""
    profiles = (
        db.query(models.DriverProfile)
        .options(joinedload(models.DriverProfile.user))
        .filter(models.DriverProfile.license_verification_status == VS.pending)
        .order_by(models.DriverProfile.updated_at.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        admin_schemas.PendingDriverOut(
            user_id=p.user_id,
            driver_profile_id=p.id,
            full_name=p.user.full_name,
            email=p.user.email,
            phone_number=p.user.phone_number,
            nin_verification_status=p.user.nin_verification_status,
            license_number=p.license_number,
            license_expiry_date=p.license_expiry_date,
            license_expired=_license_expired(p),
            license_front_url=_presign(p.license_front_url),
            license_back_url=_presign(p.license_back_url),
            license_photo_url=_presign(p.license_photo_url),
            license_verification_status=p.license_verification_status,
            license_verification_notes=p.license_verification_notes,
            can_offer_rides=p.user.can_offer_rides,
            is_driver_suspended=p.user.is_driver_suspended,
        )
        for p in profiles
    ]


# ------------------------------------------------------------
# decisions
# ------------------------------------------------------------

def _get_user_or_404(db: Session, user_id: UUID) -> models.User:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    return user


def _licence_is_valid(user: models.User) -> bool:
    p = user.driver_profile
    return bool(
        p
        and p.license_verification_status == VS.verified
        and p.license_expiry_date
        and not _license_expired(p)
    )


@router.patch(
    "/users/{user_id}/nin",
    response_model=admin_schemas.VerificationResultOut,
)
def decide_nin(
    user_id: UUID,
    decision: admin_schemas.VerificationDecision,
    db: Session = Depends(get_db),
    admin: admin_models.AdminUser = Depends(require_roles(*VERIFICATION_ROLES)),
):
    """Set a user's NIN verification status.

    verified -> user may book rides (can_book_rides = True).
    anything else -> booking is switched off again.
    """
    user = _get_user_or_404(db, user_id)

    if decision.status == VS.verified:
        if not user.nin or not user.photo_url:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "User has not submitted both a NIN and a photograph.",
            )
        user.nin_verified = True
        user.nin_verification_status = VS.verified
        user.nin_verification_notes = None
        user.can_book_rides = True
        # A driver whose NIN is re-verified gets offering back, but only
        # if their licence is still verified and unexpired.
        if _licence_is_valid(user):
            user.can_offer_rides = True
    else:
        if decision.status == VS.rejected and not (
            decision.reason and decision.reason.strip()
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "A reason is required when rejecting a NIN.",
            )
        user.nin_verified = False
        user.nin_verification_status = decision.status
        user.nin_verification_notes = decision.reason
        user.can_book_rides = False
        user.can_offer_rides = False  # drivers must have a verified NIN

    _audit(
        db, admin,
        f"NIN_{decision.status.value.upper()}",
        "users", user.id,
        decision.reason or f"NIN set to {decision.status.value}.",
    )
    db.commit()
    db.refresh(user)

    return admin_schemas.VerificationResultOut(
        user_id=user.id,
        status=user.nin_verification_status,
        can_book_rides=user.can_book_rides,
        can_offer_rides=user.can_offer_rides,
        message=f"NIN status set to {decision.status.value}.",
    )


@router.patch(
    "/drivers/{user_id}/license",
    response_model=admin_schemas.VerificationResultOut,
)
def decide_license(
    user_id: UUID,
    decision: admin_schemas.VerificationDecision,
    db: Session = Depends(get_db),
    admin: admin_models.AdminUser = Depends(require_roles(*VERIFICATION_ROLES)),
):
    """Set a driver's licence verification status.

    verified -> can_offer_rides = True (needs verified NIN, a licence
    number, an unexpired expiry date and a licence image).
    anything else -> can_offer_rides = False.
    """
    user = _get_user_or_404(db, user_id)
    profile = user.driver_profile
    if not profile:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "This user has no driver profile."
        )

    if decision.status == VS.verified:
        if user.nin_verification_status != VS.verified:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "NIN must be verified before the licence can be verified.",
            )
        if not profile.license_number or not profile.license_expiry_date:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Licence number and expiry date are required.",
            )
        if not (profile.license_front_url or profile.license_photo_url):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "No licence image has been uploaded.",
            )
        if _license_expired(profile):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Licence has expired; it cannot be verified.",
            )
        profile.license_verification_status = VS.verified
        profile.license_verification_notes = None
        user.is_driver = True
        user.can_offer_rides = True
    else:
        if decision.status == VS.rejected and not (
            decision.reason and decision.reason.strip()
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "A reason is required when rejecting a licence.",
            )
        profile.license_verification_status = decision.status
        profile.license_verification_notes = decision.reason
        user.can_offer_rides = False

    _audit(
        db, admin,
        f"LICENSE_{decision.status.value.upper()}",
        "drivers", profile.id,
        decision.reason or f"Licence set to {decision.status.value}.",
    )
    db.commit()
    db.refresh(user)

    return admin_schemas.VerificationResultOut(
        user_id=user.id,
        status=profile.license_verification_status,
        can_book_rides=user.can_book_rides,
        can_offer_rides=user.can_offer_rides,
        message=f"Licence status set to {decision.status.value}.",
    )
