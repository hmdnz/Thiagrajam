from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CarCreate(BaseModel):
    make: str
    model: str
    year: int
    color: str
    plate_number: str
    capacity: int = 4

class CarOut(CarCreate):
    id: int
    driver_id: int
    created_at: datetime

    class Config:
        from_attributes = True