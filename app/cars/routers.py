from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app import models, oauth2
from app.database import get_db
from app.cars import models as car_models, schemas as car_schemas

router = APIRouter(prefix="/cars", tags=["Cars"])

@router.post("/", response_model=car_schemas.CarOut, status_code=status.HTTP_201_CREATED)
def add_car(
    car: car_schemas.CarCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user)
):
    if current_user.role != models.UserRoleEnum.driver:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only drivers can add vehicle details")

    new_car = car_models.Car(driver_id=current_user.id, **car.model_dump())
    db.add(new_car)
    db.commit()
    db.refresh(new_car)
    return new_car

@router.get("/my-cars", response_model=List[car_schemas.CarOut])
def get_driver_cars(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user)
):
    return db.query(car_models.Car).filter(car_models.Car.driver_id == current_user.id).all()