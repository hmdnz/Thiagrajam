# """
# app/rides/schemas.py
# """

# from pydantic import BaseModel, ConfigDict, Field, model_validator
# from typing import Optional, List
# from datetime import date, time, datetime
# from decimal import Decimal


# class StopoverIn(BaseModel):
#     location: str
#     lat: Optional[float] = None
#     lng: Optional[float] = None


# class StopoverOut(StopoverIn):
#     id: int
#     sequence: int

#     model_config = ConfigDict(from_attributes=True)


# class OccurrenceOut(BaseModel):
#     id: int
#     date: date

#     model_config = ConfigDict(from_attributes=True)


# class CarSummaryOut(BaseModel):
#     """
#     Enough car info for a passenger to judge a ride by vehicle
#     type/amenities without a separate /cars/ call.
#     """

#     id: int
#     make: str
#     model: str
#     year: int
#     color: str
#     is_tinted: bool
#     has_wifi: bool
#     has_air_conditioning: bool
#     has_power_outlets: bool
#     smoking_allowed: bool
#     pets_allowed: bool
#     wheelchair_accessible: bool

#     model_config = ConfigDict(from_attributes=True)


# class RideCreate(BaseModel):
#     """
#     Payload for POST /rides/.

#     dates: 1 to 10 dates. A single date = a one-off ride.
#     More than one = a recurring ride (is_recurring is set
#     automatically based on how many dates are given).
#     """

#     car_id: int

#     pickup_location: str
#     pickup_lat: Optional[float] = None
#     pickup_lng: Optional[float] = None

#     dropoff_location: str
#     dropoff_lat: Optional[float] = None
#     dropoff_lng: Optional[float] = None

#     stopovers: List[StopoverIn] = Field(default_factory=list)

#     dates: List[date] = Field(
#         ...,
#         min_length=1,
#         max_length=10,
#     )

#     pickup_time: time

#     max_passengers: int = Field(..., ge=1)

#     # None = no restriction; 0, 1, 2, or 3 = the "max in the back" seat constraint set by the driver
#     max_back_seat_passengers: Optional[int] = Field(
#         default=None,
#         ge=0,
#         le=3,
#     )

#     instant_booking: bool = False

#     price_per_seat: Decimal = Field(..., gt=0)

#     @model_validator(mode="after")
#     def validate_ride_constraints(self):
#         # Prevent duplicate dates in multi-day / recurring ride postings
#         if len(set(self.dates)) != len(self.dates):
#             raise ValueError("Duplicate dates are not allowed.")

#         # Ensure max back seat passengers doesn't exceed total max passengers
#         if (
#             self.max_back_seat_passengers is not None
#             and self.max_back_seat_passengers > self.max_passengers
#         ):
#             raise ValueError(
#                 "max_back_seat_passengers cannot be greater than max_passengers."
#             )

#         return self


# class RideOut(BaseModel):
#     id: int
#     driver_id: int
#     car_id: int
#     pickup_location: str
#     pickup_lat: Optional[float] = None
#     pickup_lng: Optional[float] = None
#     dropoff_location: str
#     dropoff_lat: Optional[float] = None
#     dropoff_lng: Optional[float] = None
#     pickup_time: time
#     is_recurring: bool
#     max_passengers: int
#     max_back_seat_passengers: Optional[int] = None
#     instant_booking: bool
#     price_per_seat: Decimal
#     is_active: bool
#     created_at: datetime
#     stopovers: List[StopoverOut] = []
#     occurrences: List[OccurrenceOut] = []
#     car: CarSummaryOut

#     model_config = ConfigDict(from_attributes=True)


# class RideSearchResult(RideOut):
#     """
#     Same shape as RideOut, but seats_remaining is scoped to
#     the ONE searched/matched date, not every occurrence —
#     that's the number relevant to a specific search result row.
#     """

#     searched_date: date
#     seats_remaining_for_date: int



from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Optional, List
from datetime import date, time, datetime
from decimal import Decimal


class StopoverIn(BaseModel):
    location: str
    lat: Optional[float] = None
    lng: Optional[float] = None


class StopoverOut(StopoverIn):
    id: int
    sequence: int

    model_config = ConfigDict(from_attributes=True)


class OccurrenceOut(BaseModel):
    id: int
    date: date

    model_config = ConfigDict(from_attributes=True)


class CarSummaryOut(BaseModel):
    id: int
    make: str
    model: str
    year: int
    color: str
    is_tinted: bool
    has_wifi: bool
    has_air_conditioning: bool
    has_power_outlets: bool
    smoking_allowed: bool
    pets_allowed: bool
    wheelchair_accessible: bool

    model_config = ConfigDict(from_attributes=True)


class RideCreate(BaseModel):
    """
    Payload for POST /rides/.
    """
    car_id: int

    # Macro Journey (City/State level)
    origin_city: str
    origin_state: Optional[str] = None
    destination_city: str
    destination_state: Optional[str] = None

    # Micro Meeting Points
    pickup_location: str
    pickup_lat: Optional[float] = None
    pickup_lng: Optional[float] = None

    dropoff_location: str
    dropoff_lat: Optional[float] = None
    dropoff_lng: Optional[float] = None

    stopovers: List[StopoverIn] = Field(default_factory=list)

    dates: List[date] = Field(
        ...,
        min_length=1,
        max_length=10,
    )

    pickup_time: time

    max_passengers: int = Field(..., ge=1)

    max_back_seat_passengers: Optional[int] = Field(
        default=None,
        ge=0,
        le=3,
    )

    instant_booking: bool = False

    price_per_seat: Decimal = Field(..., gt=0)

    @model_validator(mode="after")
    def validate_ride_constraints(self):
        if len(set(self.dates)) != len(self.dates):
            raise ValueError("Duplicate dates are not allowed.")

        if (
            self.max_back_seat_passengers is not None
            and self.max_back_seat_passengers > self.max_passengers
        ):
            raise ValueError(
                "max_back_seat_passengers cannot be greater than max_passengers."
            )

        return self


class RideOut(BaseModel):
    id: int
    driver_id: int
    car_id: int

    # Macro Journey
    origin_city: str
    
    destination_city: str
    

    # Micro Meeting Points
    pickup_location: str
    pickup_lat: Optional[float] = None
    pickup_lng: Optional[float] = None
    dropoff_location: str
    dropoff_lat: Optional[float] = None
    dropoff_lng: Optional[float] = None

    pickup_time: time
    is_recurring: bool
    max_passengers: int
    max_back_seat_passengers: Optional[int] = None
    instant_booking: bool
    price_per_seat: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime
    stopovers: List[StopoverOut] = []
    occurrences: List[OccurrenceOut] = []
    car: CarSummaryOut

    model_config = ConfigDict(from_attributes=True)


class RideSearchResult(RideOut):
    searched_date: date
    seats_remaining_for_date: int