import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .. import models, schemas, oauth2
from ..database import get_db

router = APIRouter(prefix="/profile", tags=["Profile"])

# ==============================================================================
# 1. HELPER: IMAGE UPLOAD VALIDATION & SAVING
# shared logic for selfies and license photos
# ==============================================================================

# Acceptable formats and max size
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE_MB = 5


def save_image(file: UploadFile, subfolder: str) -> str:
    """
    Shared helper function.
    Validates file type and size, creates directories, generates a unique
    filename, writes the file, and returns the public path.
    """
    # Reject non-image types
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, or WEBP images are allowed.",
        )

    # Reject oversized files
    # (Checking contents length before writing prevents writing bad data)
    contents = file.file.read()
    if len(contents) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image must be smaller than {MAX_FILE_SIZE_MB}MB.",
        )

    # Ensure folder structure exists (e.g., static/uploads/selfies)
    folder = os.path.join("static", "uploads", subfolder)
    os.makedirs(folder, exist_ok=True)

    # Generate unique filename to prevent leaks/collisions
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(folder, filename)

    # Write contents to disk
    with open(filepath, "wb") as f:
        f.write(contents)

    # Return web-safe path with forward slashes (works on all OS)
    return f"/{filepath.replace(os.sep, '/')}"


# ==============================================================================
# 2. TEXT UPDATE ENDPOINT (PUT)
# Handles name, address, gender, NIN (locked after set)
# ==============================================================================

@router.put("/me", response_model=schemas.UserProfileOut)
def update_my_profile(
    updates: schemas.UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """
    Updates text fields (name, gender, photo_url, etc.). 
    Locks NIN after initial submission. Sets profile_complete to True upon save.
    """
    # 1. Convert Pydantic model to dictionary.
    # exclude_unset=True allows partial updates if desired, though photo_url
    # will be updated whenever supplied in the request body.
    update_data = updates.model_dump(exclude_unset=True)

    # --- Start NIN Lock Logic ---
    # Lock NIN after initial submission
    # (Allow submitting the same value, block submitting a DIFFERENT value)
    if "nin" in update_data and current_user.nin is not None:
        if update_data["nin"] != current_user.nin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="NIN has already been submitted and cannot be changed.",
            )
        del update_data["nin"]  # Drop field if it matches existing value (no-op)

    # Track if NIN is being submitted for the very first time
    submitting_new_nin = "nin" in update_data and current_user.nin is None
    # --- End NIN Lock Logic ---

    # 2. Apply updates dynamically to the current_user ORM object
    # This correctly sets full_name, photo_url, gender, blood_group, etc.
    for field, value in update_data.items():
        setattr(current_user, field, value)

    # If submitting a new NIN, reset verification status to pending
    if submitting_new_nin:
        current_user.nin_verification_status = models.VerificationStatusEnum.pending
        current_user.nin_verification_notes = None

    # 3. Force profile_complete boolean to True as requested
    current_user.profile_complete = True

    # Recalculate dynamic status if helper method exists on model
    if hasattr(current_user, "update_profile_complete"):
        current_user.update_profile_complete()
        # Re-enforce True to prevent helper method from overriding explicit setup
        current_user.profile_complete = True

    # 4. Save changes to database
    try:
        db.commit()
        db.refresh(current_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="NIN or other unique identifier already registered to another account.",
        )

    return current_user

# ==============================================================================
# 3. IMAGE UPLOAD ENDPOINTS (POST)
# Multi-part form data handles image files
# ==============================================================================

@router.post("/me/selfie", response_model=schemas.UserProfileOut)
def upload_selfie(
    file: UploadFile = File(...),   # multipart/form-data upload
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """
    Handles selfie upload separately from text profile updates.
    Enforces business logic that changing photo requires re-verification
    if a NIN is already present .
    Updates overall profile completion status .
    """
    
    # 1. Save photo using the helper. Creates public URL path .
    # Path format: /static/uploads/selfies/abc.jpg 
    current_user.photo_url = save_image(file, "selfies")


    # 2. If user already has a NIN, reset status to pending[.
    # New selfie needs reviewing against existing NIN .
    if current_user.nin:
        current_user.nin_verification_status = models.VerificationStatusEnum.pending
        current_user.nin_verification_notes = None  # clear old reasons 


    # 3. Explicitly recalculate completion, as photo_url is a strict requirement 
    current_user.update_profile_complete()

    db.commit()
    db.refresh(current_user)
    return current_user