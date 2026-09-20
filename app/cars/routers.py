# """
# app/cars/routers.py
# """

# from fastapi import (
#     APIRouter,
#     Depends,
#     HTTPException,
#     status,
#     UploadFile,
#     File,
#     Form,
    
# )
# from sqlalchemy.orm import Session
# from typing import List, Optional

# from app import models, oauth2
# from app.database import get_db
# from app.cars import models as car_models, schemas as car_schemas
# from app.s3_service import (
#     upload_car_photo,
#     delete_file_from_s3,
# )


# router = APIRouter(
#     prefix="/cars",
#     tags=["Cars"],
# )


# def _get_owned_car_or_404(
#     car_id: int,
#     current_user: models.User,
#     db: Session,
# ) -> car_models.Car:
#     """
#     Fetches a car and confirms it belongs to the current user.
#     Shared by every endpoint that acts on a specific car, so
#     the ownership check can't be forgotten on one of them.
#     """

#     car = (
#         db.query(car_models.Car)
#         .filter(car_models.Car.id == car_id)
#         .first()
#     )

#     if not car:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Car not found.",
#         )

#     if car.driver_id != current_user.id:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="You do not own this car.",
#         )

#     return car

# # ============================================================
# # ADD CAR (WITH OPTIONAL PHOTO)
# # POST /cars/
# # ============================================================

# @router.post(
#     "/",
#     response_model=car_schemas.CarOut,
#     status_code=status.HTTP_201_CREATED,
# )
# async def add_car(
#     make: str = Form(...),
#     model: str = Form(...),
#     year: int = Form(...),
#     color: str = Form(...),
#     plate_number: Optional[str] = Form(None),
#     is_tinted: bool = Form(False),
#     has_wifi: bool = Form(False),
#     has_air_conditioning: bool = Form(False),
#     has_power_outlets: bool = Form(False),
#     smoking_allowed: bool = Form(False),
#     pets_allowed: bool = Form(False),
#     wheelchair_accessible: bool = Form(False),
#     file: Optional[UploadFile] = File(None),
#     is_primary: bool = Form(True),  # <--- Added parameter for user selection
#     db: Session = Depends(get_db),
#     current_user: models.User = Depends(
#         oauth2.get_current_user
#     ),
# ):
#     """
#     Adds a car for the current user, with an optional initial photo upload.
#     The user can explicitly specify whether this photo is the primary photo via `is_primary`.
#     """

#     # 1. Instantiate the new car record
#     new_car = car_models.Car(
#         driver_id=current_user.id,
#         make=make,
#         model=model,
#         year=year,
#         color=color,
#         plate_number=plate_number,
#         is_tinted=is_tinted,
#         has_wifi=has_wifi,
#         has_air_conditioning=has_air_conditioning,
#         has_power_outlets=has_power_outlets,
#         smoking_allowed=smoking_allowed,
#         pets_allowed=pets_allowed,
#         wheelchair_accessible=wheelchair_accessible,
#     )

#     db.add(new_car)

#     # Flush assigns an ID to new_car without finalizing the transaction
#     try:
#         db.flush()
#     except Exception as error:
#         db.rollback()
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to initialize car creation. Error: {str(error)}",
#         )

#     s3_key = None

#     # 2. Process optional photo upload if a file was provided
#     if file and file.filename:
#         try:
#             file_content = await file.read()
#         except Exception as error:
#             db.rollback()
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail=f"Unable to read uploaded image. Error: {str(error)}",
#             )

#         try:
#             s3_key = upload_car_photo(
#                 file_content=file_content,
#                 content_type=file.content_type,
#                 car_id=new_car.id,
#             )
#         except ValueError as error:
#             db.rollback()
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail=str(error),
#             )
#         except RuntimeError as error:
#             db.rollback()
#             raise HTTPException(
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                 detail=str(error),
#             )

#         # Attach photo record using the user-selected `is_primary` value
#         new_photo = car_models.CarPhoto(
#             car_id=new_car.id,
#             photo_url=s3_key,
#             is_primary=is_primary,  # <--- Uses the form field value
#         )
#         db.add(new_photo)

#     # 3. Commit the transaction and handle rollback cleanups
#     try:
#         db.commit()
#         db.refresh(new_car)
#     except Exception as error:
#         db.rollback()

#         # Clean up uploaded S3 image if DB commit fails
#         if s3_key:
#             delete_file_from_s3(s3_key)

#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to complete car record save. Error: {str(error)}",
#         )

#     return new_car

# # ============================================================
# # MY CARS
# # GET /cars/my-cars
# # ============================================================

# @router.get(
#     "/my-cars",
#     response_model=List[car_schemas.CarOut],
# )
# def get_driver_cars(
#     db: Session = Depends(get_db),
#     current_user: models.User = Depends(
#         oauth2.get_current_user
#     ),
# ):
#     return (
#         db.query(car_models.Car)
#         .filter(car_models.Car.driver_id == current_user.id)
#         .all()
#     )


# # ============================================================
# # UPDATE CAR
# # PUT /cars/{car_id}
# # ============================================================

# @router.put(
#     "/{car_id}",
#     response_model=car_schemas.CarOut,
# )
# def update_car(
#     car_id: int,
#     updates: car_schemas.CarUpdate,
#     db: Session = Depends(get_db),
#     current_user: models.User = Depends(
#         oauth2.get_current_user
#     ),
# ):
#     car = _get_owned_car_or_404(
#         car_id=car_id,
#         current_user=current_user,
#         db=db,
#     )

#     update_data = updates.model_dump(exclude_unset=True)

#     for field, value in update_data.items():
#         setattr(car, field, value)

#     db.commit()
#     db.refresh(car)

#     return car


# # ============================================================
# # DELETE CAR
# # DELETE /cars/{car_id}
# # ============================================================

# @router.delete(
#     "/{car_id}",
#     status_code=status.HTTP_204_NO_CONTENT,
# )
# def delete_car(
#     car_id: int,
#     db: Session = Depends(get_db),
#     current_user: models.User = Depends(
#         oauth2.get_current_user
#     ),
# ):
#     car = _get_owned_car_or_404(
#         car_id=car_id,
#         current_user=current_user,
#         db=db,
#     )

#     # Delete photos from S3 before deleting the row — the
#     # cascade will remove the CarPhoto rows, but not the
#     # actual S3 objects, so that has to happen here explicitly.
#     for photo in car.photos:
#         delete_file_from_s3(photo.photo_url)

#     db.delete(car)
#     db.commit()

#     return None


# # ============================================================
# # UPLOAD CAR PHOTO
# # POST /cars/{car_id}/photos
# # ============================================================

# @router.post(
#     "/{car_id}/photos",
#     response_model=car_schemas.CarOut,
# )
# async def upload_car_photo_endpoint(
#     car_id: int,
#     file: UploadFile = File(...),
#     is_primary: bool = False,
#     db: Session = Depends(get_db),
#     current_user: models.User = Depends(
#         oauth2.get_current_user
#     ),
# ):
#     """
#     Uploads one photo for a car. Call this once per photo —
#     the frontend can call it repeatedly to build up a gallery.

#     Type/size/empty-file validation all happens inside
#     upload_car_photo (via validate_image in s3_service.py) —
#     this endpoint doesn't duplicate those checks, it just
#     reads the file and translates whatever upload_car_photo
#     raises into the right HTTP response.
#     """

#     car = _get_owned_car_or_404(
#         car_id=car_id,
#         current_user=current_user,
#         db=db,
#     )

#     try:
#         file_content = await file.read()

#     except Exception as error:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail=(
#                 "Unable to read uploaded image. "
#                 f"Error: {str(error)}"
#             ),
#         )

#     try:
#         photo_key = upload_car_photo(
#             file_content=file_content,
#             content_type=file.content_type,
#             car_id=car.id,
#         )

#     except ValueError as error:
#         # Raised by validate_image for bad type / empty /
#         # oversized files — a client error, not a server one.
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail=str(error),
#         )

#     except RuntimeError as error:
#         # Raised when the S3 put_object call itself fails.
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=str(error),
#         )

#     # If this photo is marked primary, unset any existing
#     # primary photo first so there's only ever one.
#     if is_primary:
#         for existing_photo in car.photos:
#             existing_photo.is_primary = False

#     new_photo = car_models.CarPhoto(
#         car_id=car.id,
#         photo_url=photo_key,
#         is_primary=is_primary,
#     )

#     db.add(new_photo)
#     db.commit()
#     db.refresh(car)

#     return car



from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Form,
)
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional

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
    Fetches a car with photos eager-loaded and confirms it belongs to the current user.
    """
    car = (
        db.query(car_models.Car)
        .options(joinedload(car_models.Car.photos))
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
# ADD CAR (WITH OPTIONAL PHOTO)
# POST /cars/
# ============================================================


@router.post(
    "/",
    response_model=car_schemas.CarOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_car(
    make: str = Form(...),
    model: str = Form(...),
    year: int = Form(...),
    color: str = Form(...),
    plate_number: Optional[str] = Form(None),
    capacity: int = Form(4),
    is_tinted: bool = Form(False),
    has_wifi: bool = Form(False),
    has_air_conditioning: bool = Form(False),
    has_power_outlets: bool = Form(False),
    smoking_allowed: bool = Form(False),
    pets_allowed: bool = Form(False),
    wheelchair_accessible: bool = Form(False),
    
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    """Adds a car for the current user, with an optional initial photo upload."""

    # 1. Instantiate the new car record
    new_car = car_models.Car(
    driver_id=current_user.id,
    make=make,
    model=model,
    year=year,
    color=color,
    plate_number=plate_number, 
    capacity=capacity,
    is_tinted=is_tinted,
    has_wifi=has_wifi,
    has_air_conditioning=has_air_conditioning,
    has_power_outlets=has_power_outlets,
    smoking_allowed=smoking_allowed,
    pets_allowed=pets_allowed,
    wheelchair_accessible=wheelchair_accessible,
)
    db.add(new_car)

    try:
        db.flush()
    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize car creation. Error: {str(error)}",
        )

    s3_key = None

    # 2. Process optional photo upload if a file was provided
    if file and file.filename:
        try:
            file_content = await file.read()
        except Exception as error:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unable to read uploaded image. Error: {str(error)}",
            )

        try:
            s3_key = upload_car_photo(
                file_content=file_content,
                content_type=file.content_type,
                car_id=new_car.id,
            )
        except ValueError as error:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            )
        except RuntimeError as error:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(error),
            )

        new_photo = car_models.CarPhoto(
            car_id=new_car.id,
            photo_url=s3_key,
            
        )
        db.add(new_photo)

    # 3. Commit transaction and load full object state
    try:
        db.commit()

        # Re-fetch with photos eager-loaded
        created_car = (
            db.query(car_models.Car)
            .options(joinedload(car_models.Car.photos))
            .filter(car_models.Car.id == new_car.id)
            .first()
        )
        return created_car

    except Exception as error:
        db.rollback()

        if s3_key:
            delete_file_from_s3(s3_key)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete car record save. Error: {str(error)}",
        )


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
    current_user: models.User = Depends(oauth2.get_current_user),
):
    return (
        db.query(car_models.Car)
        .options(joinedload(car_models.Car.photos))
        .filter(car_models.Car.driver_id == current_user.id)
        .all()
    )


# # ============================================================
# # UPDATE CAR
# # PUT /cars/{car_id}
# # ============================================================


# @router.put(
#     "/{car_id}",
#     response_model=car_schemas.CarOut,
# )
# def update_car(
#     car_id: int,
#     updates: car_schemas.CarUpdate,
#     db: Session = Depends(get_db),
#     current_user: models.User = Depends(oauth2.get_current_user),
# ):
#     car = _get_owned_car_or_404(
#         car_id=car_id,
#         current_user=current_user,
#         db=db,
#     )

#     update_data = updates.model_dump(exclude_unset=True)

#     for field, value in update_data.items():
#         setattr(car, field, value)

#     db.commit()

#     # Re-query car to ensure all fields and photos are freshly populated
#     updated_car = (
#         db.query(car_models.Car)
#         .options(joinedload(car_models.Car.photos))
#         .filter(car_models.Car.id == car_id)
#         .first()
#     )

#     return updated_car
# UPDATE CAR
# PATCH /cars/{car_id}
# ============================================================


@router.patch(
    "/{car_id}",
    response_model=car_schemas.CarOut,
)
def update_car(
    car_id: int,
    updates: car_schemas.CarUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
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

    # Re-query car to ensure all fields and photos are freshly populated
    updated_car = (
        db.query(car_models.Car)
        .options(joinedload(car_models.Car.photos))
        .filter(car_models.Car.id == car_id)
        .first()
    )

    return updated_car

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
    current_user: models.User = Depends(oauth2.get_current_user),
):
    car = _get_owned_car_or_404(
        car_id=car_id,
        current_user=current_user,
        db=db,
    )

    # 1. Delete associated photos from S3 safely
    for photo in car.photos:
        try:
            delete_file_from_s3(photo.photo_url)
        except Exception as error:
            # Log S3 failure without crashing the DB deletion process (or handle appropriately)
            print(f"Failed to delete photo {photo.photo_url} from S3: {str(error)}")

    # 2. Delete car from Database
    try:
        db.delete(car)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete car because it is referenced by existing rides or bookings.",
        )
    except Exception as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete car from database: {str(error)}",
        )

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
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
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
            detail=f"Unable to read uploaded image. Error: {str(error)}",
        )

    try:
        photo_key = upload_car_photo(
            file_content=file_content,
            content_type=file.content_type,
            car_id=car.id,
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

    # if is_primary:
    #     for existing_photo in car.photos:
    #         existing_photo.is_primary = False

    new_photo = car_models.CarPhoto(
        car_id=car.id,
       
        photo_url=photo_key
    )

    db.add(new_photo)
    db.commit()

    updated_car = (
        db.query(car_models.Car)
        .options(joinedload(car_models.Car.photos))
        .filter(car_models.Car.id == car.id)
        .first()
    )

    return updated_car