from fastapi import (APIRouter,Depends,HTTPException,status,
                     UploadFile,File,
)
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .. import models, schemas, oauth2
from ..database import get_db
from ..s3_service import (
    upload_profile_image,
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


# ============================================================
# CHECK IF PROFILE INFORMATION IS COMPLETE
# EXCEPT FOR PHOTO
# ============================================================

def profile_information_complete(
    user: models.User,
) -> bool:
    """
    Checks whether the user has completed all required
    profile information BEFORE uploading a profile photo.

    photo_url is intentionally NOT checked here because
    this function determines whether the user is allowed
    to upload a photo.
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
# UPDATE PROFILE INFORMATION
# PUT /profile/me
# ============================================================

@router.put(
    "/me",
    response_model=schemas.UserProfileOut,
)
def update_my_profile(
    updates: schemas.UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Updates the user's profile information.

    IMPORTANT:
    profile_complete is NOT manually set to True.

    The profile becomes complete only when:
    1. All required information is filled
    2. The user has uploaded a profile photo
    """

    # ========================================================
    # CONVERT SUBMITTED FIELDS TO DICTIONARY
    # ========================================================

    update_data = updates.model_dump(
        exclude_unset=True
    )

    # ========================================================
    # NIN LOCK LOGIC
    # ========================================================

    if (
        "nin" in update_data
        and current_user.nin is not None
    ):

        # User cannot change an existing NIN
        if update_data["nin"] != current_user.nin:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "NIN has already been submitted "
                    "and cannot be changed."
                ),
            )

        # Same NIN submitted again.
        # Nothing needs to be changed.
        del update_data["nin"]

    # ========================================================
    # CHECK IF THIS IS FIRST NIN SUBMISSION
    # ========================================================

    submitting_new_nin = (
        "nin" in update_data
        and current_user.nin is None
    )

    # ========================================================
    # UPDATE USER FIELDS
    # ========================================================

    for field, value in update_data.items():

        # photo_url must only be changed through
        # the photo upload endpoint.
        if field == "photo_url":
            continue

        setattr(
            current_user,
            field,
            value,
        )

    # ========================================================
    # NIN VERIFICATION STATUS
    # ========================================================

    if submitting_new_nin:

        current_user.nin_verification_status = (
            models.VerificationStatusEnum.pending
        )

        current_user.nin_verification_notes = None

    # ========================================================
    # UPDATE PROFILE COMPLETION STATUS
    # ========================================================

    current_user.update_profile_complete()

    # ========================================================
    # SAVE DATABASE
    # ========================================================

    try:

        db.commit()

        db.refresh(
            current_user
        )

    except IntegrityError:

        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "NIN or another unique identifier "
                "already belongs to another user."
            ),
        )

    return current_user


# ============================================================
# UPLOAD PROFILE PHOTO
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
    Uploads the user's profile photo to AWS S3.

    The user cannot upload a photo until all required
    profile information has been completed.

    After successful upload:
    - photo_url is saved
    - profile completion is recalculated
    - profile_complete becomes True when all required
      information and the photo are present
    """

    # ========================================================
    # STEP 1: CHECK PROFILE INFORMATION
    # ========================================================

    if not profile_information_complete(
        current_user
    ):

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
            detail=(
                "Only JPEG, PNG, or WEBP images "
                "are allowed."
            ),
        )

    # ========================================================
    # STEP 3: READ FILE CONTENT
    # ========================================================

    try:

        file_content = await file.read()

    except Exception as error:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unable to read uploaded image. "
                f"Error: {str(error)}"
            ),
        )

    # ========================================================
    # STEP 4: CHECK FILE SIZE
    # ========================================================

    max_size = (
        MAX_FILE_SIZE_MB
        * 1024
        * 1024
    )

    if len(file_content) > max_size:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Image must be smaller than "
                f"{MAX_FILE_SIZE_MB}MB."
            ),
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
            detail=(
                "Failed to upload profile photo. "
                f"Error: {str(error)}"
            ),
        )

    # ========================================================
    # SAFETY CHECK
    # ========================================================

    if not new_photo_key:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Profile photo was uploaded but "
                "no S3 file key was returned."
            ),
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

        db.refresh(
            current_user
        )

    except Exception as error:

        db.rollback()

        # Database failed after S3 upload.
        # Remove the newly uploaded photo so that
        # we don't leave an orphaned S3 object.

        if new_photo_key:

            try:

                delete_file_from_s3(
                    new_photo_key
                )

            except Exception as delete_error:

                print(
                    "Warning: Failed to delete newly "
                    f"uploaded S3 photo: {delete_error}"
                )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Failed to save profile photo "
                f"information. Error: {str(error)}"
            ),
        )

    # ========================================================
    # STEP 11: DELETE OLD PHOTO
    # ========================================================

    # Only delete the old photo AFTER the database
    # successfully stores the new photo.

    if (
        old_photo_key
        and old_photo_key != new_photo_key
    ):

        try:

            delete_file_from_s3(
                old_photo_key
            )

        except Exception as error:

            # Do not fail the request because the new
            # photo has already been successfully saved.

            print(
                "Warning: Failed to delete old "
                f"S3 photo: {error}"
            )

    # ========================================================
    # STEP 12: RETURN UPDATED USER
    # ========================================================

    return current_user

