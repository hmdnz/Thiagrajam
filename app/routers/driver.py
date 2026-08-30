from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .. import models, schemas, oauth2
from ..database import get_db
from .profile import save_image  # reuse the same upload/validation helper as selfies

# All routes here live under /profile/driver/... — keeps driver-specific
# endpoints clearly separated from the general passenger profile routes.
router = APIRouter(prefix="/profile/driver", tags=["Driver Profile"])


def _get_driver_profile(current_user: models.User, db: Session) -> models.DriverProfile:
    """Fetches the current user's DriverProfile, lazily creating an empty
    row if it doesn't exist. Requires the account to already be in
    'driver' role (set via POST /profile/me/become-driver)."""

    # Guard: a passenger account has no business touching driver-only data.
    if current_user.role != models.UserRoleEnum.driver:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Switch to a driver role first via POST /profile/me/become-driver.",
        )

    # The relationship is defined as uselist=False in models.py, so this
    # is either a single DriverProfile object or None — never a list.
    driver_profile = current_user.driver_profile

    if not driver_profile:
        # Safety net: normally become_driver() already creates this row,
        # but this covers any account that switched to driver role before
        # that logic existed, or via some other path.
        driver_profile = models.DriverProfile(user_id=current_user.id)
        db.add(driver_profile)
        db.commit()
        db.refresh(driver_profile)  # pulls back the generated id, defaults, etc.

    return driver_profile


@router.get("", response_model=schemas.DriverProfileOut)
def get_driver_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),  # who's asking
):
    """Returns the logged-in driver's licence info and verification status."""
    # db is passed through even though this route only reads, because
    # _get_driver_profile may need to create+commit a new row on first call.
    return _get_driver_profile(current_user, db)


@router.put("", response_model=schemas.DriverProfileOut)
def update_driver_profile(
    payload: schemas.DriverProfileUpdate,      # validated request body
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """Updates licence number and/or expiry date. Licence photo is
    uploaded separately via POST /profile/driver/license-photo."""
    driver_profile = _get_driver_profile(current_user, db)

    # exclude_unset=True means only fields the client actually sent end up
    # here — omitted fields are left untouched rather than reset to None.
    update_data = payload.model_dump(exclude_unset=True)

    # Licence number is permanently fixed once first submitted — same
    # reasoning as NIN elsewhere in the app: prevents quietly swapping in
    # a different real person's licence after initial approval.
    if "license_number" in update_data and driver_profile.license_number is not None:
        if update_data["license_number"] != driver_profile.license_number:
            # Genuinely trying to change it — reject.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Licence number has already been submitted and cannot be changed.",
            )
        # Same value sent again (e.g. form re-submits everything each save) —
        # treat as a no-op rather than an error.
        del update_data["license_number"]

    # Apply whatever's left (license_number if new, and/or license_expiry_date).
    for field, value in update_data.items():
        setattr(driver_profile, field, value)

    # Any genuine change here means the previous admin approval (if any)
    # no longer applies to the current data — force re-review.
    if update_data:
        driver_profile.license_verification_status = models.VerificationStatusEnum.pending
        driver_profile.license_verification_notes = None  # clear any old rejection reason

    try:
        db.commit()
        db.refresh(driver_profile)
    except IntegrityError:
        # Most likely cause: license_number collides with another driver's
        # (it's a unique column) — surface a clear message instead of a raw 500.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Licence number already registered to another account.",
        )

    # Driver-side changes can flip the overall profile_complete flag on
    # the User row (see User.update_profile_complete in models.py),
    # so recompute it and commit that separately.
    current_user.update_profile_complete()
    db.commit()

    return driver_profile


@router.post("/license-photo", response_model=schemas.DriverProfileOut)
def upload_license_photo(
    file: UploadFile = File(...),   # multipart file upload, not JSON
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """Handles the licence photo upload separately from the JSON update,
    since file uploads use multipart/form-data, not JSON."""
    driver_profile = _get_driver_profile(current_user, db)

    # save_image validates file type/size, writes to static/uploads/licenses/,
    # and returns the public URL path to store on the model.
    driver_profile.license_photo_url = save_image(file, "licenses")

    # A new/changed licence photo always needs a fresh admin look,
    # regardless of whether license_number/expiry also changed.
    driver_profile.license_verification_status = models.VerificationStatusEnum.pending
    driver_profile.license_verification_notes = None

    db.commit()
    db.refresh(driver_profile)

    # Same reasoning as above: photo completeness feeds into profile_complete.
    current_user.update_profile_complete()
    db.commit()

    return driver_profile