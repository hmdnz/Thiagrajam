import uuid
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from .config import settings


# ============================================================
# S3 CLIENT
# ============================================================

s3_client = boto3.client(
    "s3",
    region_name=settings.AWS_REGION,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
)


# ============================================================
# IMAGE CONFIGURATION
# ============================================================

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

MAX_FILE_SIZE_MB = 5
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def validate_image(file_content: bytes, content_type: str):
    """
    Validate uploaded image.
    """

    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError(
            "Only JPEG, PNG, or WEBP images are allowed."
        )

    if len(file_content) == 0:
        raise ValueError(
            "Uploaded file is empty."
        )

    if len(file_content) > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"Image must be smaller than {MAX_FILE_SIZE_MB}MB."
        )


def upload_profile_image(
    *,
    file_content: bytes,
    content_type: str,
    user_id: int,
) -> str:
    """
    Upload a user's profile image to S3.

    Returns:
        S3 object key
    """

    validate_image(file_content, content_type)

    # Get the correct extension
    extension = ALLOWED_IMAGE_TYPES[content_type]

    # Generate unique filename
    filename = f"{uuid.uuid4().hex}{extension}"

    # S3 folder structure
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
            f"Failed to upload image to S3: {error}"
        )

    return s3_key


def delete_file_from_s3(s3_key: str):
    """
    Delete an old file from S3.
    """

    if not s3_key:
        return

    try:

        s3_client.delete_object(
            Bucket=settings.AWS_S3_BUCKET,
            Key=s3_key,
        )

    except ClientError:
        # Don't crash profile update if old image
        # cannot be deleted.
        pass


def generate_presigned_url(
    s3_key: str,
    expires_in: int = 3600,
) -> str:
    """
    Generate temporary private URL for frontend.
    """

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