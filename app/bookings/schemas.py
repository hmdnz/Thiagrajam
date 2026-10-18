"""
app/bookings/schemas.py

Pydantic request/response schemas for the Wenyfour booking module.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.bookings.models import (
    BookingStatusEnum,
    CancellationRefundStatusEnum,
    CancellationTypeEnum,
)


# ============================================================
# BOOKING CREATION
# ============================================================


class BookingCreate(BaseModel):
    ride_id: int = Field(
        ...,
        gt=0,
    )

    travel_date: date

    seats_booked: int = Field(
        default=1,
        ge=1,
    )


# ============================================================
# BOOKING RESPONSE
# ============================================================


class BookingOut(BaseModel):
    id: int

    passenger_id: UUID

    ride_id: int

    car_id: Optional[int] = None

    travel_date: date

    seats_booked: int

    fare: Decimal

    status: BookingStatusEnum

    driver_confirmed_at: Optional[datetime] = None

    trip_started_at: Optional[datetime] = None

    trip_completed_at: Optional[datetime] = None

    funds_released_at: Optional[datetime] = None

    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


# ============================================================
# DRIVER CONFIRMATION
# ============================================================


class BookingDriverConfirm(BaseModel):
    note: Optional[str] = Field(
        default=None,
        max_length=500,
    )


# ============================================================
# DRIVER REJECTION
# ============================================================


class BookingDriverReject(BaseModel):
    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
    )


# ============================================================
# TRIP ACTION
# ============================================================


class BookingTripAction(BaseModel):
    note: Optional[str] = Field(
        default=None,
        max_length=500,
    )


# ============================================================
# DRIVER PASSENGER BOOKING VIEW
# ============================================================


class DriverPassengerBookingOut(BaseModel):
    booking_id: int

    passenger_id: UUID

    passenger_name: Optional[str] = None

    passenger_email: Optional[str] = None

    passenger_phone: Optional[str] = None

    ride_id: int

    travel_date: date

    pickup_time: time

    pickup_location: str

    dropoff_location: str

    seats_booked: int

    fare: Decimal

    status: BookingStatusEnum

    created_at: datetime

    driver_confirmed_at: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True,
    )


# ============================================================
# CANCELLATION REQUEST
# ============================================================


class BookingCancellationRequest(BaseModel):
    reason: Optional[str] = Field(
        default=None,
        max_length=500,
    )


# ============================================================
# CANCELLATION RESPONSE
# ============================================================


class BookingCancellationOut(BaseModel):
    message: str

    booking_id: int

    cancellation_type: CancellationTypeEnum

    original_fare_kobo: int

    penalty_kobo: int

    passenger_refund_kobo: int

    passenger_voucher_kobo: int

    driver_voucher_kobo: int

    company_share_kobo: int

    driver_wallet_charge_kobo: int

    refund_required: bool

    refund_requested: bool

    refund_status: CancellationRefundStatusEnum

    model_config = ConfigDict(
        from_attributes=True,
    )
