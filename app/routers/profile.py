"""
app/routers/profile.py

Unified profile router — passenger and driver information both
live under /profile, since every user starts as a passenger and
can optionally build out a driver profile alongside it.

Key design point (per business rules in models.py):
- Filling in driver info is NOT gated on NIN verification or 
  passenger-profile completeness. Anyone can start a driver application at any time.
- The actual restrictions —
    "can't publish a ride until licence is verified"
    "can't complete a booking until NIN is verified"
  — are checked at those actions (in the booking module), using
  current_user.can_offer_rides / current_user.can_book_rides.
  This router does not enforce either of those; it only stores
  the data that those checks will later depend on.
"""

from datetime import date
from typing import Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Form,
)
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .. import models, schemas, oauth2
from ..database import get_db
from ..s3_service import (
    upload_profile_image,
    upload_driver_license_image,
    delete_file_from_s3,
)


router = APIRouter(
    prefix="/profile",
    tags=["Profile"],
)


# ============================================================
# IMAGE SETTINGS
# ============================================================

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_FILE_SIZE_MB = 5
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Fields that live on DriverProfile rather than User for PUT /profile/me.
# (license_number and license_expiry_date are excluded here as they are managed via /profile/driver/license-photo)
DRIVER_FIELD_NAMES = {
    "about_me",
    "chattiness",
    "music",
    "smoking",
    "pets",
}


# ============================================================
# HELPERS — PASSENGER PROFILE
# ============================================================

def profile_information_complete(
    user: models.User,
) -> bool:
    """
    Checks whether the user has completed all required
    passenger profile information BEFORE uploading a
    profile photo (photo_url is excluded here, since this
    function decides whether a photo can be uploaded).
    """

    required_fields = [
        user.full_name,
        user.address,
        user.phone_number,
        user.date_of_birth,
        user.gender,
        user.next_of_kin_name,
        user.emergency_contact,
        user.blood_group,
        user.nin,
    ]

    return all(
        field is not None
        for field in required_fields
    )


# ============================================================
# HELPERS — DRIVER PROFILE
# ============================================================

def _get_or_create_driver_profile(
    current_user: models.User,
    db: Session,
) -> models.DriverProfile:
    """
    Returns the user's driver profile, creating an empty one
    if it doesn't exist yet.

    No eligibility check happens here on purpose — starting a
    driver profile has no prerequisites. Publish/booking-time
    restrictions live in the booking module instead.

    Handles the race condition where two requests try to
    create the driver profile at the same time.
    """

    driver_profile = current_user.driver_profile

    if driver_profile:
        return driver_profile

    driver_profile = models.DriverProfile(
        user_id=current_user.id
    )

    db.add(driver_profile)

    try:
        db.commit()
        db.refresh(driver_profile)
    except IntegrityError:
        db.rollback()
        driver_profile = (
            db.query(models.DriverProfile)
            .filter(
                models.DriverProfile.user_id == current_user.id
            )
            .first()
        )

        if not driver_profile:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to create driver profile.",
            )

    return driver_profile


# ============================================================
# GET COMBINED PROFILE
# GET /profile/me
# ============================================================

@router.get(
    "/me",
    response_model=schemas.UserProfileOut,
)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Returns the current user's passenger profile, with the
    driver profile (if one exists) nested via the
    driver_profile field on UserProfileOut. If the user has
    never touched any driver field, driver_profile is null.
    """

    return current_user


# ============================================================
# UPDATE COMBINED PROFILE (PASSENGER + DRIVER PREFERENCES)
# PUT /profile/me
# JSON body — photos and driver license details are handled separately.
# ============================================================

@router.put(
    "/me",
    response_model=schemas.UserProfileOut,
)
def update_my_profile(
    updates: schemas.ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Single endpoint that updates passenger information and driver 
    preferences (about_me, chattiness, music, smoking, pets).

    Note: License details (license_number, license_expiry_date) 
    must be updated via POST /profile/driver/license-photo.
    """

    # ========================================================
    # CONVERT SUBMITTED FIELDS TO DICTIONARY
    # ========================================================

    update_data = updates.model_dump(
        exclude_unset=True
    )

    # Ignore license details if passed into PUT /profile/me
    update_data.pop("license_number", None)
    update_data.pop("license_expiry_date", None)

    # ========================================================
    # SPLIT SUBMITTED FIELDS INTO PASSENGER / DRIVER
    # ========================================================

    passenger_data = {
        field: value
        for field, value in update_data.items()
        if field not in DRIVER_FIELD_NAMES
    }

    driver_data = {
        field: value
        for field, value in update_data.items()
        if field in DRIVER_FIELD_NAMES
    }

    # ========================================================
    # PASSENGER — NIN LOCK LOGIC
    # ========================================================

    if (
        "nin" in passenger_data
        and current_user.nin is not None
    ):
        if passenger_data["nin"] != current_user.nin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "NIN has already been submitted "
                    "and cannot be changed."
                ),
            )
        # Same NIN submitted again — nothing to change.
        del passenger_data["nin"]

    submitting_new_nin = (
        "nin" in passenger_data
        and current_user.nin is None
    )

    # ========================================================
    # PASSENGER — APPLY FIELD UPDATES
    # ========================================================

    for field, value in passenger_data.items():
        # photo_url must only be changed through the
        # dedicated photo upload endpoint below.
        if field == "photo_url":
            continue

        setattr(
            current_user,
            field,
            value,
        )

    if submitting_new_nin:
        current_user.nin_verification_status = (
            models.VerificationStatusEnum.pending
        )
        current_user.nin_verification_notes = None

    # current_user.update_profile_complete()

    # ========================================================
    # DRIVER PREFERENCES — APPLY FIELD UPDATES
    # ========================================================

    driver_profile = None

    if driver_data:
        driver_profile = _get_or_create_driver_profile(
            current_user=current_user,
            db=db,
        )

        for field, value in driver_data.items():
            setattr(
                driver_profile,
                field,
                value,
            )

        # --------------------------------------------------
        # BUMP UNVERIFIED -> PENDING ONCE APPLICATION IS FULL
        # --------------------------------------------------

        if driver_profile.is_complete():
            if (
                driver_profile.license_verification_status
                == models.VerificationStatusEnum.unverified
            ):
                driver_profile.license_verification_status = (
                    models.VerificationStatusEnum.pending
                )
                driver_profile.license_verification_notes = None

    # ========================================================
    # SAVE DATABASE
    # ========================================================

    try:
        db.commit()
        db.refresh(current_user)

        if driver_profile:
            db.refresh(driver_profile)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "NIN already belongs to another user."
            ),
        )

    return current_user


# ============================================================
# UPLOAD PROFILE (SELFIE) PHOTO
# POST /profile/me/photo
# ============================================================

@router.post(
    "/me/photo",
    response_model=schemas.UserProfileOut,
)
async def upload_profile_photo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Uploads the user's profile (selfie) photo to AWS S3.
    """

    # ========================================================
    # STEP 1: CHECK PROFILE INFORMATION
    # ========================================================

    if not profile_information_complete(current_user):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Please complete all required profile "
                "information before uploading your photo."
            ),
        )

    # ========================================================
    # STEP 2: VALIDATE FILE TYPE
    # ========================================================

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, or WEBP images are allowed.",
        )

    # ========================================================
    # STEP 3: READ FILE CONTENT
    # ========================================================

    try:
        file_content = await file.read()
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to read uploaded image. Error: {str(error)}",
        )

    # ========================================================
    # STEP 4: CHECK FILE SIZE
    # ========================================================

    if len(file_content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image must be smaller than {MAX_FILE_SIZE_MB}MB.",
        )

    # ========================================================
    # STEP 5: STORE OLD PHOTO KEY
    # ========================================================

    old_photo_key = current_user.photo_url

    # ========================================================
    # STEP 6: UPLOAD NEW PHOTO TO S3
    # ========================================================

    new_photo_key = None

    try:
        new_photo_key = upload_profile_image(
            file_content=file_content,
            content_type=file.content_type,
            user_id=current_user.id,
        )
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload profile photo. Error: {str(error)}",
        )

    if not new_photo_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile photo was uploaded but no S3 file key was returned.",
        )

    # ========================================================
    # STEP 7: SAVE NEW S3 KEY
    # ========================================================

    current_user.photo_url = new_photo_key

    # ========================================================
    # STEP 8: UPDATE NIN VERIFICATION STATUS
    # ========================================================

    if current_user.nin:
        current_user.nin_verification_status = (
            models.VerificationStatusEnum.pending
        )
        current_user.nin_verification_notes = None

    # ========================================================
    # STEP 9: UPDATE PROFILE COMPLETION
    # ========================================================

    current_user.update_profile_complete()

    # ========================================================
    # STEP 10: SAVE DATABASE
    # ========================================================

    try:
        db.commit()
        db.refresh(current_user)
    except Exception as error:
        db.rollback()

        if new_photo_key:
            try:
                delete_file_from_s3(new_photo_key)
            except Exception as delete_error:
                print(
                    "Warning: Failed to delete newly "
                    f"uploaded S3 photo: {delete_error}"
                )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save profile photo information. Error: {str(error)}",
        )

    # ========================================================
    # STEP 11: DELETE OLD PHOTO
    # ========================================================

    if old_photo_key and old_photo_key != new_photo_key:
        try:
            delete_file_from_s3(old_photo_key)
        except Exception as error:
            print(f"Warning: Failed to delete old S3 photo: {error}")

    return current_user


# ============================================================
# UPLOAD DRIVER LICENCE PHOTO & DETAILS
# POST /profile/driver/license-photo
# ============================================================

@router.post(
    "/driver/license-photo",
    response_model=schemas.UserProfileOut,
)
async def upload_license_photo(
    license_number: Optional[str] = Form(None, description="Driver's licence number"),
    license_expiry_date: Optional[date] = Form(None, description="Licence expiration date (YYYY-MM-DD)"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Uploads the driver's licence photo to AWS S3 along with the
    licence number and expiry date via form data in a single request.
    """

    # ========================================================
    # GET OR CREATE DRIVER PROFILE
    # ========================================================

    driver_profile = _get_or_create_driver_profile(
        current_user=current_user,
        db=db,
    )

    # ========================================================
    # LICENCE NUMBER PROTECTION
    # ========================================================

    if license_number is not None:
        if (
            driver_profile.license_number is not None
            and driver_profile.license_number != license_number
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Licence number has already been "
                    "submitted and cannot be changed."
                ),
            )

        driver_profile.license_number = license_number

    # ========================================================
    # LICENCE EXPIRY DATE UPDATES
    # ========================================================

    if license_expiry_date is not None:
        driver_profile.license_expiry_date = license_expiry_date

    # ========================================================
    # FILE TYPE VALIDATION
    # ========================================================

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPEG, PNG, or WEBP images are allowed.",
        )

    # ========================================================
    # READ FILE
    # ========================================================

    try:
        file_content = await file.read()
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to read uploaded licence image. Error: {str(error)}",
        )

    # ========================================================
    # FILE SIZE VALIDATION
    # ========================================================

    if len(file_content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded licence image is empty.",
        )

    if len(file_content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Licence image must be smaller than {MAX_FILE_SIZE_MB}MB.",
        )

    # ========================================================
    # OLD PHOTO
    # ========================================================

    old_license_photo_key = driver_profile.license_photo_url
    new_license_photo_key = None

    # ========================================================
    # UPLOAD TO S3
    # ========================================================

    try:
        new_license_photo_key = upload_driver_license_image(
            file_content=file_content,
            content_type=file.content_type,
            user_id=current_user.id,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        )
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload licence photo. Error: {str(error)}",
        )

    if not new_license_photo_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Licence photo was uploaded but no S3 file key was returned.",
        )

    # ========================================================
    # SAVE NEW KEY & RESET VERIFICATION
    # ========================================================

    driver_profile.license_photo_url = new_license_photo_key

    driver_profile.license_verification_status = (
        models.VerificationStatusEnum.pending
    )
    driver_profile.license_verification_notes = None

    # ========================================================
    # BUMP UNVERIFIED -> PENDING ONCE APPLICATION IS FULL
    # ========================================================

    if driver_profile.is_complete():
        driver_profile.license_verification_status = (
            models.VerificationStatusEnum.pending
        )
        driver_profile.license_verification_notes = None

    # ========================================================
    # SAVE DATABASE
    # ========================================================

    try:
        db.commit()
        db.refresh(current_user)
        db.refresh(driver_profile)

    except IntegrityError:
        db.rollback()
        if new_license_photo_key:
            try:
                delete_file_from_s3(new_license_photo_key)
            except Exception as delete_error:
                print(
                    "Warning: Failed to delete newly uploaded licence photo from S3: "
                    f"{delete_error}"
                )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Licence number already belongs to another user.",
        )

    except Exception as error:
        db.rollback()
        if new_license_photo_key:
            try:
                delete_file_from_s3(new_license_photo_key)
            except Exception as delete_error:
                print(
                    "Warning: Failed to delete newly uploaded licence photo from S3: "
                    f"{delete_error}"
                )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save licence photo information. Error: {str(error)}",
        )

    # ========================================================
    # DELETE OLD PHOTO
    # ========================================================

    if old_license_photo_key and old_license_photo_key != new_license_photo_key:
        try:
            delete_file_from_s3(old_license_photo_key)
        except Exception as error:
            print(f"Warning: Failed to delete old licence photo: {error}")

    return current_user