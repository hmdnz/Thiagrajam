"""
app/cars/routers.py
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
)
from sqlalchemy.orm import Session
from typing import List

from app import models, oauth2
from app.database import get_db
from app.cars import models as car_models, schemas as car_schemas
from app.s3_service import (
    upload_car_photo,
    delete_file_from_s3,
)


router = APIRouter(
    prefix="/cars",
    tags=["Cars"],
)


def _get_owned_car_or_404(
    car_id: int,
    current_user: models.User,
    db: Session,
) -> car_models.Car:
    """
    Fetches a car and confirms it belongs to the current user.
    Shared by every endpoint that acts on a specific car, so
    the ownership check can't be forgotten on one of them.
    """

    car = (
        db.query(car_models.Car)
        .filter(car_models.Car.id == car_id)
        .first()
    )

    if not car:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Car not found.",
        )

    if car.driver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this car.",
        )

    return car


# ============================================================
# ADD CAR
# POST /cars/
# ============================================================

@router.post(
    "/",
    response_model=car_schemas.CarOut,
    status_code=status.HTTP_201_CREATED,
)
def add_car(
    car: car_schemas.CarCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Adds a car for the current user.

    No eligibility gate: adding a car is one more piece of
    building a driver profile, same as submitting a licence
    number, and has no prerequisite. Whether the resulting
    rides can actually be PUBLISHED is a separate check, done
    in the rides router against current_user.can_offer_rides.
    """

    new_car = car_models.Car(
        driver_id=current_user.id,
        **car.model_dump(),
    )

    db.add(new_car)
    db.commit()
    db.refresh(new_car)

    return new_car


# ============================================================
# MY CARS
# GET /cars/my-cars
# ============================================================

@router.get(
    "/my-cars",
    response_model=List[car_schemas.CarOut],
)
def get_driver_cars(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),
):
    return (
        db.query(car_models.Car)
        .filter(car_models.Car.driver_id == current_user.id)
        .all()
    )


# ============================================================
# UPDATE CAR
# PUT /cars/{car_id}
# ============================================================

@router.put(
    "/{car_id}",
    response_model=car_schemas.CarOut,
)
def update_car(
    car_id: int,
    updates: car_schemas.CarUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),
):
    car = _get_owned_car_or_404(
        car_id=car_id,
        current_user=current_user,
        db=db,
    )

    update_data = updates.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(car, field, value)

    db.commit()
    db.refresh(car)

    return car


# ============================================================
# DELETE CAR
# DELETE /cars/{car_id}
# ============================================================

@router.delete(
    "/{car_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_car(
    car_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),
):
    car = _get_owned_car_or_404(
        car_id=car_id,
        current_user=current_user,
        db=db,
    )

    # Delete photos from S3 before deleting the row — the
    # cascade will remove the CarPhoto rows, but not the
    # actual S3 objects, so that has to happen here explicitly.
    for photo in car.photos:
        delete_file_from_s3(photo.photo_url)

    db.delete(car)
    db.commit()

    return None


# ============================================================
# UPLOAD CAR PHOTO
# POST /cars/{car_id}/photos
# ============================================================

@router.post(
    "/{car_id}/photos",
    response_model=car_schemas.CarOut,
)
async def upload_car_photo_endpoint(
    car_id: int,
    file: UploadFile = File(...),
    is_primary: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(
        oauth2.get_current_user
    ),
):
    """
    Uploads one photo for a car. Call this once per photo —
    the frontend can call it repeatedly to build up a gallery.

    Type/size/empty-file validation all happens inside
    upload_car_photo (via validate_image in s3_service.py) —
    this endpoint doesn't duplicate those checks, it just
    reads the file and translates whatever upload_car_photo
    raises into the right HTTP response.
    """

    car = _get_owned_car_or_404(
        car_id=car_id,
        current_user=current_user,
        db=db,
    )

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

    try:
        photo_key = upload_car_photo(
            file_content=file_content,
            content_type=file.content_type,
            car_id=car.id,
        )

    except ValueError as error:
        # Raised by validate_image for bad type / empty /
        # oversized files — a client error, not a server one.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    except RuntimeError as error:
        # Raised when the S3 put_object call itself fails.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
        )

    # If this photo is marked primary, unset any existing
    # primary photo first so there's only ever one.
    if is_primary:
        for existing_photo in car.photos:
            existing_photo.is_primary = False

    new_photo = car_models.CarPhoto(
        car_id=car.id,
        photo_url=photo_key,
        is_primary=is_primary,
    )

    db.add(new_photo)
    db.commit()
    db.refresh(car)

    return car

