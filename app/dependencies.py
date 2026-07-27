from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from . import models, oauth2
from .database import get_db

PROFILE_REQUIRED_FIELDS = ["full_name", "address", "phone_number", "nin", "date_of_birth"]


def is_profile_complete(profile: "models.User") -> bool:
    return all(getattr(profile, field) is not None for field in PROFILE_REQUIRED_FIELDS)


def require_complete_profile(
    current_user: models.User = Depends(oauth2.get_current_user),
    db: Session = Depends(get_db)
) -> models.User:
    """Use as a route dependency to block access until onboarding is done.
    e.g. def create_post(..., current_user = Depends(dependencies.require_complete_profile))"""

    profile = db.query(models.User).filter(
        models.User.user_id == current_user.id
    ).first()

    if not profile or not is_profile_complete(profile):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please complete your profile before continuing."
        )

    return current_user