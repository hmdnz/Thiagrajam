# app/routers/driver.py

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
)

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .. import models, schemas, oauth2
from ..database import get_db
from ..s3_service import (
    upload_driver_license_image,
    delete_file_from_s3,
)


router = APIRouter(
    prefix="/profile/driver",
    tags=["Driver Profile"],
)


# ============================================================
# DRIVER PROFILE HELPERS
# ============================================================

def _get_or_create_driver_profile(
    current_user: models.User,
    db: Session,
) -> models.DriverProfile:

    driver_profile = current_user.driver_profile

    if driver_profile:
        return driver_profile

    driver_profile = models.DriverProfile(
        user_id=current_user.id
    )

    db.add(driver_profile)

    try:

        db.commit()

        db.refresh(
            driver_profile
        )

    except IntegrityError:

        db.rollback()

        driver_profile = (
            db.query(models.DriverProfile)
            .filter(
                models.DriverProfile.user_id
                == current_user.id
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
# DRIVER APPLICATION ELIGIBILITY
# ============================================================

def _require_driver_application_eligibility(
    current_user: models.User,
):
    """
    A user must:

    1. Complete the common profile.
    2. Have a verified NIN.

    before applying to become a driver.
    """

    if not current_user.profile_complete:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Please complete your passenger profile "
                "before applying to become a driver."
            ),
        )

    if (
        current_user.nin_verification_status
        != models.VerificationStatusEnum.verified
    ):

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Your NIN must be verified before "
                "you can apply to become a driver."
            ),
        )


# ============================================================
# GET DRIVER PROFILE
# GET /profile/driver
# ============================================================

@router.get(
    "",
    response_model=schemas.DriverProfileOut,
)
def get_driver_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),
):

    return _get_or_create_driver_profile(
        current_user=current_user,
        db=db,
    )


# ============================================================
# UPDATE DRIVER PROFILE
# PUT /profile/driver
# ============================================================

@router.put(
    "",
    response_model=schemas.DriverProfileOut,
)
def update_driver_profile(
    payload: schemas.DriverProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),
):

    # ========================================================
    # CHECK PASSENGER PROFILE + NIN
    # ========================================================

    _require_driver_application_eligibility(
        current_user
    )

    # ========================================================
    # GET OR CREATE DRIVER PROFILE
    # ========================================================

    driver_profile = _get_or_create_driver_profile(
        current_user=current_user,
        db=db,
    )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    if not update_data:
        return driver_profile

    # ========================================================
    # LICENCE NUMBER PROTECTION
    # ========================================================

    if (
        "license_number" in update_data
        and driver_profile.license_number is not None
    ):

        submitted_license_number = (
            update_data["license_number"]
        )

        existing_license_number = (
            driver_profile.license_number
        )

        if (
            submitted_license_number
            != existing_license_number
        ):

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Licence number has already been "
                    "submitted and cannot be changed."
                ),
            )

        del update_data["license_number"]

    # ========================================================
    # CHECK WHETHER LICENCE VERIFICATION IS AFFECTED
    # ========================================================

    verification_required = any(
        field in update_data
        for field in [
            "license_number",
            "license_expiry_date",
        ]
    )

    # ========================================================
    # UPDATE DRIVER FIELDS
    # ========================================================

    for field, value in update_data.items():

        setattr(
            driver_profile,
            field,
            value,
        )

    # ========================================================
    # RESET VERIFICATION WHEN LICENCE INFORMATION CHANGES
    # ========================================================

    if verification_required:

        driver_profile.license_verification_status = (
            models.VerificationStatusEnum.pending
        )

        driver_profile.license_verification_notes = None

    # ========================================================
    # DRIVER PROFILE COMPLETE
    # ========================================================

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
    # SAVE
    # ========================================================

    try:

        db.commit()

        db.refresh(
            driver_profile
        )

    except IntegrityError:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Licence number is already registered "
                "to another account."
            ),
        )

    return driver_profile


# ============================================================
# UPLOAD DRIVER LICENCE PHOTO
# POST /profile/driver/license-photo
# ============================================================

@router.post(
    "/license-photo",
    response_model=schemas.DriverProfileOut,
)
async def upload_license_photo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),
):

    # ========================================================
    # CHECK PASSENGER PROFILE + NIN
    # ========================================================

    _require_driver_application_eligibility(
        current_user
    )

    # ========================================================
    # GET DRIVER PROFILE
    # ========================================================

    driver_profile = _get_or_create_driver_profile(
        current_user=current_user,
        db=db,
    )

    # ========================================================
    # FILE TYPE
    # ========================================================

    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    if file.content_type not in allowed_types:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Only JPEG, PNG, or WEBP images "
                "are allowed."
            ),
        )

    # ========================================================
    # READ FILE
    # ========================================================

    try:

        file_content = await file.read()

    except Exception as error:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unable to read uploaded licence image. "
                f"Error: {str(error)}"
            ),
        )

    # ========================================================
    # SIZE
    # ========================================================

    max_size = 5 * 1024 * 1024

    if len(file_content) == 0:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded licence image is empty.",
        )

    if len(file_content) > max_size:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Licence image must be smaller than 5MB."
            ),
        )

    # ========================================================
    # OLD PHOTO
    # ========================================================

    old_license_photo_key = (
        driver_profile.license_photo_url
    )

    new_license_photo_key = None

    # ========================================================
    # UPLOAD TO S3
    # ========================================================

    try:

        new_license_photo_key = (
            upload_driver_license_image(
                file_content=file_content,
                content_type=file.content_type,
                user_id=current_user.id,
            )
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
            detail=(
                "Failed to upload licence photo. "
                f"Error: {str(error)}"
            ),
        )

    if not new_license_photo_key:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Licence photo was uploaded but "
                "no S3 file key was returned."
            ),
        )

    # ========================================================
    # SAVE NEW KEY
    # ========================================================

    driver_profile.license_photo_url = (
        new_license_photo_key
    )

    # ========================================================
    # LICENCE MUST BE VERIFIED AGAIN
    # ========================================================

    driver_profile.license_verification_status = (
        models.VerificationStatusEnum.pending
    )

    driver_profile.license_verification_notes = None

    # ========================================================
    # SAVE DATABASE
    # ========================================================

    try:

        db.commit()

        db.refresh(
            driver_profile
        )

    except Exception as error:

        db.rollback()

        if new_license_photo_key:

            try:

                delete_file_from_s3(
                    new_license_photo_key
                )

            except Exception as delete_error:

                print(
                    "Warning: Failed to delete newly "
                    "uploaded licence photo from S3: "
                    f"{delete_error}"
                )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Failed to save licence photo "
                f"information. Error: {str(error)}"
            ),
        )

    # ========================================================
    # DELETE OLD PHOTO
    # ========================================================

    if (
        old_license_photo_key
        and old_license_photo_key
        != new_license_photo_key
    ):

        try:

            delete_file_from_s3(
                old_license_photo_key
            )

        except Exception as error:

            print(
                "Warning: Failed to delete old "
                "licence photo: "
                f"{error}"
            )

    return driver_profile