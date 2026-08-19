from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .. import models, schemas, oauth2
from ..database import get_db

router = APIRouter(
    prefix="/profile",
    tags=["Profile"]
)

# Fields required before the profile counts as "complete."
REQUIRED_FIELDS = ["full_name", "address", "phone_number", "nin", "date_of_birth"]


def _is_complete(user: models.User) -> bool:
    return all(getattr(user, field) is not None for field in REQUIRED_FIELDS)


@router.put("", response_model=schemas.UserProfileOut)
def update_my_profile(
    updates: schemas.UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user)
):
    """Updates the logged-in user's own profile. Accepts partial data —
    only the fields sent in the request body get changed."""

    user = db.query(models.User).filter(
    models.User.id == current_user.id
).first()


    # Guard in case a profile row wasn't created at signup (e.g. accounts
    # that existed before this feature was added).
    if not user:
        raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="User not found"
    )


    for field, value in updates.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    try:
        db.commit()
        db.refresh(user)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="NIN already registered to another account."
        )

    result = schemas.UserProfileOut.model_validate(user)
    result.is_complete = _is_complete(user)
    return result