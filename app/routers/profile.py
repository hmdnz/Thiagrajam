import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .. import models, schemas, oauth2
from ..database import get_db

router = APIRouter(prefix="/profile", tags=["Profile"])

# Only these image types are accepted for selfie/licence uploads.
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE_MB = 5


def save_image(file: UploadFile, subfolder: str) -> str:
    """Validates and saves an uploaded image under static/uploads/<subfolder>/,
    returning the public URL path to store on the model (photo_url or
    license_photo_url). Shared by both profile.py (selfies) and
    driver.py (licence photos) so validation logic stays in one place."""

    # Reject anything that isn't an accepted image MIME type.
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, or WEBP images are allowed.",
        )

    contents = file.file.read()

    # Reject oversized uploads before writing anything to disk.
    if len(contents) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image must be smaller than {MAX_FILE_SIZE_MB}MB.",
        )

    # Group uploads by type (selfies/ vs licenses/) for easier admin review.
    folder = os.path.join("static", "uploads", subfolder)
    os.makedirs(folder, exist_ok=True)

    # Random filename avoids collisions and avoids leaking the original filename.
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(folder, filename)

    with open(filepath, "wb") as f:
        f.write(contents)

    # Return a web-safe forward-slash path regardless of OS (Windows uses backslashes).
    return f"/{filepath.replace(os.sep, '/')}"


@router.get("/me", response_model=schemas.UserProfileOut)
def get_my_profile(current_user: models.User = Depends(oauth2.get_current_user)):
    """Returns the logged-in user's own profile — no lookup needed since
    get_current_user already resolved the User row from the JWT."""
    return current_user


@router.put("/me", response_model=schemas.UserProfileOut)
def update_my_profile(
    updates: schemas.UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """Updates the logged-in user's own profile. Accepts partial data —
    only fields sent in the request body get changed (multi-step form
    friendly)."""
    user = db.query(models.User).filter(models.User.id == current_user.id).first()

    # Guard in case a profile row wasn't created at signup (e.g. accounts
    # that existed before this feature was added).
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Only take the fields the client actually sent, ignoring anything unset.
    update_data = updates.model_dump(exclude_unset=True)

    # NIN is permanently fixed once first submitted — a person's national ID
    # number shouldn't be editable after the fact. Allow resubmitting the
    # exact same value (e.g. the form re-sends the whole payload each save)
    # but block any attempt to change it to something different.
    if "nin" in update_data and user.nin is not None:
        if update_data["nin"] != user.nin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="NIN has already been submitted and cannot be changed.",
            )
        del update_data["nin"]  # no-op change, drop it so setattr loop below skips it

    # Track whether this is a brand-new NIN submission (vs re-sending old data)
    # so we know whether to flip it into "pending" for admin review.
    submitting_new_nin = "nin" in update_data and user.nin is None

    for field, value in update_data.items():
        setattr(user, field, value)

    # A freshly submitted NIN needs an admin to manually check it against the selfie.
    if submitting_new_nin:
        user.nin_verification_status = models.VerificationStatusEnum.pending
        user.nin_verification_notes = None  # clear any stale rejection reason

    # Recompute whether the profile now counts as fully complete.
    user.update_profile_complete()

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        # Most likely cause: NIN collides with another user's unique NIN.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="NIN already registered to another account.",
        )

    return user


@router.post("/me/selfie", response_model=schemas.UserProfileOut)
def upload_selfie(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """Handles the selfie upload separately from the JSON profile update,
    since file uploads use multipart/form-data, not JSON."""
    current_user.photo_url = save_image(file, "selfies")

    # A new/changed selfie needs re-checking against the NIN, even if the
    # NIN itself hasn't changed — the photo is half of what gets verified.
    if current_user.nin:
        current_user.nin_verification_status = models.VerificationStatusEnum.pending
        current_user.nin_verification_notes = None

    current_user.update_profile_complete()
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/become-driver", response_model=schemas.UserProfileOut)
def become_driver(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """Switches the account to driver role and creates an empty
    DriverProfile row if one doesn't exist yet. Call this before
    hitting any /profile/driver/* endpoint."""
    if current_user.role != models.UserRoleEnum.driver:
        current_user.role = models.UserRoleEnum.driver

    # Only create a DriverProfile if this is genuinely the first time —
    # avoids wiping out any licence data from a previous stint as a driver.
    if not current_user.driver_profile:
        db.add(models.DriverProfile(user_id=current_user.id))

    current_user.update_profile_complete()
    db.commit()
    db.refresh(current_user)
    return current_user