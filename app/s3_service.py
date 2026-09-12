# app/s3_service.py

import uuid

import boto3
from botocore.exceptions import ClientError

from .config import settings


# ============================================================
# AWS S3 CLIENT
# ============================================================

s3_client = boto3.client(
    "s3",
    region_name=settings.AWS_REGION,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
)


# ============================================================
# IMAGE SETTINGS
# ============================================================

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

MAX_FILE_SIZE_MB = 5
MAX_FILE_SIZE_BYTES = (
    MAX_FILE_SIZE_MB * 1024 * 1024
)


# ============================================================
# VALIDATE IMAGE
# ============================================================

def validate_image(
    file_content: bytes,
    content_type: str,
):
    """
    Validates uploaded image content.

    Allowed:
        JPEG
        PNG
        WEBP

    Maximum:
        5 MB
    """

    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError(
            "Only JPEG, PNG, or WEBP images are allowed."
        )

    if not file_content:
        raise ValueError(
            "Uploaded file is empty."
        )

    if len(file_content) > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"Image must be smaller than "
            f"{MAX_FILE_SIZE_MB}MB."
        )


# ============================================================
# UPLOAD PROFILE IMAGE
# ============================================================

def upload_profile_image(
    *,
    file_content: bytes,
    content_type: str,
    user_id: int,
) -> str:
    """
    Uploads a user's profile photo.

    S3 path:

        users/{user_id}/profile/{filename}
    """

    validate_image(
        file_content=file_content,
        content_type=content_type,
    )

    extension = ALLOWED_IMAGE_TYPES[
        content_type
    ]

    filename = (
        f"{uuid.uuid4().hex}"
        f"{extension}"
    )

    s3_key = (
        f"users/{user_id}/profile/{filename}"
    )

    try:

        s3_client.put_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType=content_type,
        )

    except ClientError as error:

        raise RuntimeError(
            f"Failed to upload profile image to S3: {error}"
        )

    return s3_key


# ============================================================
# UPLOAD DRIVER LICENCE IMAGE
# ============================================================

def upload_driver_license_image(
    *,
    file_content: bytes,
    content_type: str,
    user_id: int,
) -> str:
    """
    Uploads a driver's licence photo.

    S3 path:

        users/{user_id}/driver/license/{filename}

    This is deliberately separate from the normal
    profile-photo path.
    """

    validate_image(
        file_content=file_content,
        content_type=content_type,
    )

    extension = ALLOWED_IMAGE_TYPES[
        content_type
    ]

    filename = (
        f"{uuid.uuid4().hex}"
        f"{extension}"
    )

    s3_key = (
        f"users/{user_id}/driver/license/{filename}"
    )

    try:

        s3_client.put_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType=content_type,
        )

    except ClientError as error:

        raise RuntimeError(
            f"Failed to upload driver licence image to S3: {error}"
        )

    return s3_key


# ============================================================
# UPLOAD CAR PHOTO
# ============================================================

def upload_car_photo(
    *,
    file_content: bytes,
    content_type: str,
    car_id: int,
) -> str:
    """
    Uploads a photo of a car.

    S3 path:

        cars/{car_id}/photos/{filename}

    A car can have several photos, so unlike profile/licence
    uploads this is called once per photo rather than once
    per user — each call gets its own filename and doesn't
    overwrite the last one.
    """

    validate_image(
        file_content=file_content,
        content_type=content_type,
    )

    extension = ALLOWED_IMAGE_TYPES[
        content_type
    ]

    filename = (
        f"{uuid.uuid4().hex}"
        f"{extension}"
    )

    s3_key = (
        f"cars/{car_id}/photos/{filename}"
    )

    try:

        s3_client.put_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType=content_type,
        )

    except ClientError as error:

        raise RuntimeError(
            f"Failed to upload car photo to S3: {error}"
        )

    return s3_key



# ============================================================
# DELETE FILE FROM S3
# ============================================================

def delete_file_from_s3(
    s3_key: str,
):
    """
    Deletes a file from S3.

    Failure to delete is intentionally ignored so that
    an S3 cleanup problem does not break an otherwise
    successful database operation.
    """

    if not s3_key:
        return

    try:

        s3_client.delete_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=s3_key,
        )

    except ClientError:
        pass


# ============================================================
# GENERATE PRESIGNED URL
# ============================================================

def generate_presigned_url(
    s3_key: str,
    expires_in: int = 3600,
) -> str:
    """
    Generates a temporary URL for accessing a private
    S3 object.
    """

    if not s3_key:
        raise ValueError(
            "S3 file key is required."
        )

    try:

        return s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": settings.AWS_S3_BUCKET,
                "Key": s3_key,
            },
            ExpiresIn=expires_in,
        )

    except ClientError as error:

        raise RuntimeError(
            f"Failed to generate image URL: {error}"
        )