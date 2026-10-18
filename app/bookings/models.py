"""
app/bookings/models.py

Booking domain models for Wenyfour.

Responsibilities:
- Booking lifecycle
- Driver/passenger cancellation records
- Passenger/driver cancellation financial snapshots
- Ride vouchers
- Audit timestamps

IMPORTANT:
- Monetary values used for payment/cancellation accounting are stored in kobo
  as integers.
- Booking.fare remains Numeric(10, 2) because it represents the booking fare
  in NGN at the booking layer.
- Financial mutations should be performed transactionally through the
  payments ledger/service layer.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


# ============================================================
# ENUMS
# ============================================================


class BookingStatusEnum(str, enum.Enum):
    """
    Booking lifecycle.

    PENDING:
        Booking request exists and is awaiting driver action/payment flow.

    CONFIRMED:
        Driver has accepted the passenger.

    TRIP_STARTED:
        Driver has started the trip.

    TRIP_COMPLETED:
        Driver has completed the trip.

    CANCELLED:
        Booking was cancelled by passenger or driver.

    REFUNDED:
        Booking has completed its refund process.
    """

    PENDING = "pending"
    CONFIRMED = "confirmed"
    TRIP_STARTED = "trip_started"
    TRIP_COMPLETED = "trip_completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class CancellationTypeEnum(str, enum.Enum):
    PASSENGER = "passenger"
    DRIVER = "driver"


class CancellationRefundStatusEnum(str, enum.Enum):
    """
    Refund workflow attached to a booking cancellation.

    NOT_REQUIRED:
        No refund is due.

    REQUIRED:
        Refund is due but has not yet been requested.

    REQUESTED:
        Passenger has requested the refund.

    APPROVED:
        Refund has been approved internally.

    PROCESSING:
        Provider refund is being processed.

    COMPLETED:
        Refund completed successfully.

    FAILED:
        Refund attempt failed and requires reconciliation/retry.
    """

    NOT_REQUIRED = "not_required"
    REQUIRED = "required"
    REQUESTED = "requested"
    APPROVED = "approved"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================
# BOOKING
# ============================================================


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    passenger_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    ride_id = Column(
        Integer,
        ForeignKey("rides.id"),
        nullable=False,
        index=True,
    )

    car_id = Column(
        Integer,
        ForeignKey("cars.id"),
        nullable=True,
        index=True,
    )

    travel_date = Column(
        Date,
        nullable=False,
        index=True,
    )

    seats_booked = Column(
        Integer,
        nullable=False,
        default=1,
    )

    # Booking fare in NGN.
    # Payment/cancellation calculations convert this to integer kobo.
    fare = Column(
        Numeric(10, 2),
        nullable=False,
    )

    status = Column(
        SQLEnum(
            BookingStatusEnum,
            name="bookingstatusenum",
            values_callable=lambda values: [item.value for item in values],
        ),
        default=BookingStatusEnum.PENDING,
        nullable=False,
        index=True,
    )

    driver_confirmed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    trip_started_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    trip_completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    funds_released_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ========================================================
    # RELATIONSHIPS
    # ========================================================

    passenger = relationship(
        "User",
        back_populates="bookings",
    )

    ride = relationship(
        "Ride",
        back_populates="bookings",
    )

    car = relationship(
        "app.cars.models.Car",
        back_populates="bookings",
    )

    payments = relationship(
        "Payment",
        back_populates="booking",
    )

    cancellation = relationship(
        "BookingCancellation",
        back_populates="booking",
        uselist=False,
        cascade="all, delete-orphan",
    )

    vouchers = relationship(
        "RideVoucher",
        back_populates="booking",
        passive_deletes=True,
    )


# ============================================================
# BOOKING CANCELLATION
# ============================================================


class BookingCancellation(Base):
    __tablename__ = "booking_cancellations"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    booking_id = Column(
        Integer,
        ForeignKey(
            "bookings.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
    )

    cancelled_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    cancellation_type = Column(
        SQLEnum(
            CancellationTypeEnum,
            name="cancellationtypeenum",
            values_callable=lambda values: [item.value for item in values],
        ),
        nullable=False,
        index=True,
    )

    reason = Column(
        String,
        nullable=True,
    )

    # ========================================================
    # FINANCIAL SNAPSHOT
    # ========================================================

    # Original booking amount in kobo.
    original_fare_kobo = Column(
        Integer,
        nullable=False,
    )

    # Cancellation penalty in kobo.
    penalty_kobo = Column(
        Integer,
        nullable=False,
        default=0,
    )

    # Amount the passenger is entitled to receive as a refund.
    passenger_refund_kobo = Column(
        Integer,
        nullable=False,
        default=0,
    )

    # Voucher issued to passenger.
    passenger_voucher_kobo = Column(
        Integer,
        nullable=False,
        default=0,
    )

    # Voucher issued to driver.
    driver_voucher_kobo = Column(
        Integer,
        nullable=False,
        default=0,
    )

    # Company share from cancellation penalty.
    company_share_kobo = Column(
        Integer,
        nullable=False,
        default=0,
    )

    # Actual debit applied to driver's available wallet.
    driver_wallet_charge_kobo = Column(
        Integer,
        nullable=False,
        default=0,
    )

    # ========================================================
    # REFUND WORKFLOW
    # ========================================================

    refund_required = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    refund_requested = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    refund_status = Column(
        SQLEnum(
            CancellationRefundStatusEnum,
            name="cancellationrefundstatusenum",
            values_callable=lambda values: [item.value for item in values],
        ),
        nullable=False,
        default=CancellationRefundStatusEnum.NOT_REQUIRED,
        index=True,
    )

    refund_requested_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    refund_completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    refund_reference = Column(
        String,
        nullable=True,
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ========================================================
    # RELATIONSHIPS
    # ========================================================

    booking = relationship(
        "Booking",
        back_populates="cancellation",
    )

    cancelled_by = relationship(
        "User",
        foreign_keys=[cancelled_by_id],
    )


# ============================================================
# RIDE VOUCHER
# ============================================================


class RideVoucher(Base):
    """
    Internal Wenyfour voucher.

    Examples:
    - Passenger cancellation:
        Driver receives 5% of booking value as voucher.
    - Driver cancellation:
        Passenger receives 5% of booking value as voucher.

    Voucher value is stored in integer kobo.
    """

    __tablename__ = "ride_vouchers"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    booking_id = Column(
        Integer,
        ForeignKey(
            "bookings.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    amount_kobo = Column(
        Integer,
        nullable=False,
    )

    used_kobo = Column(
        Integer,
        nullable=False,
        default=0,
    )

    reason = Column(
        String,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ========================================================
    # RELATIONSHIPS
    # ========================================================

    user = relationship(
        "User",
    )

    booking = relationship(
        "Booking",
        back_populates="vouchers",
    )
