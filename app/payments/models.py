"""
app/payments/models.py
"""

import enum
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    Enum,
    TIMESTAMP,
    Numeric,
    Date,
    Text,
    Index,
    text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


# ============================================================
# ENUMS
# ============================================================

class PaymentProviderEnum(enum.Enum):
    squad = "squad"
    paystack = "paystack"


class PaymentStatusEnum(enum.Enum):
    pending = "pending"
    success = "success"
    failed = "failed"


class PaymentPurposeEnum(enum.Enum):
    booking = "booking"
    wallet_topup = "wallet_topup"


class TransactionTypeEnum(enum.Enum):
    payment = "payment"
    refund = "refund"
    payout = "payout"
    commission = "commission"
    tax = "tax"
    adjustment = "adjustment"


class RefundStatusEnum(enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    processed = "processed"
    failed = "failed"


class PayoutStatusEnum(enum.Enum):
    pending = "pending"
    processing = "processing"
    success = "success"
    failed = "failed"
    reversed = "reversed"


class StatementStatusEnum(enum.Enum):
    draft = "draft"
    issued = "issued"


# ============================================================
# PAYMENT
# ============================================================

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    booking_id = Column(
        Integer,
        ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    purpose = Column(
        Enum(PaymentPurposeEnum),
        default=PaymentPurposeEnum.booking,
        nullable=False,
    )

    provider = Column(Enum(PaymentProviderEnum), nullable=False)

    transaction_ref = Column(String, unique=True, nullable=False, index=True)
    provider_ref = Column(String, nullable=True)

    amount_kobo = Column(Integer, nullable=False)
    merchant_amount_kobo = Column(Integer, nullable=True)

    currency = Column(String, default="NGN", nullable=False)

    status = Column(
        Enum(PaymentStatusEnum),
        default=PaymentStatusEnum.pending,
        nullable=False,
        index=True,
    )

    raw_status = Column(String, nullable=True)
    auth_url = Column(String, nullable=True)
    failure_reason = Column(Text, nullable=True)
    provider_response = Column(Text, nullable=True)

    paid_at = Column(TIMESTAMP(timezone=True), nullable=True)

    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    user = relationship("User", backref="payments")
    booking = relationship("Booking", backref="payments")
    transactions = relationship(
        "Transaction",
        back_populates="payment",
        cascade="all, delete-orphan",
    )
    refunds = relationship(
        "Refund",
        back_populates="payment",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_payments_user_status", "user_id", "status"),
    )


# ============================================================
# TRANSACTION (LEDGER)
# ============================================================

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    payment_id = Column(
        Integer,
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    booking_id = Column(
        Integer,
        ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payout_id = Column(
        Integer,
        ForeignKey("payouts.id", ondelete="SET NULL"),
        nullable=True,
    )
    refund_id = Column(
        Integer,
        ForeignKey("refunds.id", ondelete="SET NULL"),
        nullable=True,
    )

    transaction_type = Column(Enum(TransactionTypeEnum), nullable=False)

    # "credit" = money in, "debit" = money out
    direction = Column(String, nullable=False)

    amount_kobo = Column(Integer, nullable=False)
    currency = Column(String, default="NGN", nullable=False)
    description = Column(String, nullable=True)
    provider_ref = Column(String, nullable=True)

    transaction_date = Column(Date, nullable=False)

    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    payment = relationship("Payment", back_populates="transactions")
    user = relationship("User", backref="transactions")

    __table_args__ = (
        Index("ix_transactions_user_date", "user_id", "transaction_date"),
    )


# ============================================================
# REFUND
# ============================================================

class Refund(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, index=True)

    payment_id = Column(
        Integer,
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    booking_id = Column(
        Integer,
        ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    refund_ref = Column(String, unique=True, nullable=False, index=True)
    provider_refund_ref = Column(String, nullable=True)

    is_partial = Column(Boolean, default=False, nullable=False)
    amount_kobo = Column(Integer, nullable=False)
    currency = Column(String, default="NGN", nullable=False)
    reason = Column(Text, nullable=False)

    status = Column(
        Enum(RefundStatusEnum),
        default=RefundStatusEnum.pending,
        nullable=False,
        index=True,
    )

    raw_status = Column(String, nullable=True)
    admin_note = Column(Text, nullable=True)
    processed_at = Column(TIMESTAMP(timezone=True), nullable=True)

    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    payment = relationship("Payment", back_populates="refunds")
    booking = relationship("Booking", backref="refunds")
    requested_by = relationship(
        "User", foreign_keys=[requested_by_id], backref="refunds_requested"
    )
    reviewed_by = relationship(
        "User", foreign_keys=[reviewed_by_id], backref="refunds_reviewed"
    )


# ============================================================
# PAYOUT
# ============================================================

class Payout(Base):
    __tablename__ = "payouts"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    payout_ref = Column(String, unique=True, nullable=False, index=True)
    provider_ref = Column(String, nullable=True)
    provider = Column(Enum(PaymentProviderEnum), nullable=False)

    gross_amount_kobo = Column(Integer, nullable=False)
    commission_kobo = Column(Integer, nullable=False)
    tax_kobo = Column(Integer, nullable=False)
    net_amount_kobo = Column(Integer, nullable=False)

    currency = Column(String, default="NGN", nullable=False)

    bank_code = Column(String, nullable=False)
    bank_name = Column(String, nullable=True)
    account_number = Column(String, nullable=False)
    account_name = Column(String, nullable=False)
    recipient_code = Column(String, nullable=True)

    status = Column(
        Enum(PayoutStatusEnum),
        default=PayoutStatusEnum.pending,
        nullable=False,
        index=True,
    )

    raw_status = Column(String, nullable=True)
    failure_reason = Column(Text, nullable=True)
    admin_note = Column(Text, nullable=True)
    processed_at = Column(TIMESTAMP(timezone=True), nullable=True)

    created_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    driver = relationship("User", backref="payouts")


# ============================================================
# STATEMENT
# ============================================================

class Statement(Base):
    __tablename__ = "statements"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))

    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    opening_balance_kobo = Column(Integer, nullable=False, default=0)
    closing_balance_kobo = Column(Integer, nullable=False, default=0)
    total_credits_kobo = Column(Integer, nullable=False, default=0)
    total_debits_kobo = Column(Integer, nullable=False, default=0)
    total_commission_kobo = Column(Integer, nullable=False, default=0)
    total_tax_kobo = Column(Integer, nullable=False, default=0)

    currency = Column(String, default="NGN", nullable=False)

    status = Column(
        Enum(StatementStatusEnum),
        default=StatementStatusEnum.issued,
        nullable=False,
    )

    generated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    user = relationship("User", backref="statements")

    __table_args__ = (
        Index(
            "ix_statements_user_period",
            "user_id",
            "period_start",
            "period_end",
        ),
    )


# ============================================================
# WALLET
# ============================================================

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))

    available_balance_kobo = Column(Integer, nullable=False, default=0)
    pending_balance_kobo = Column(Integer, nullable=False, default=0)

    lifetime_credits_kobo = Column(Integer, nullable=False, default=0)
    lifetime_debits_kobo = Column(Integer, nullable=False, default=0)
    lifetime_commission_kobo = Column(Integer, nullable=False, default=0)
    lifetime_tax_kobo = Column(Integer, nullable=False, default=0)

    currency = Column(String, default="NGN", nullable=False)

    updated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    user = relationship("User", backref="wallet", uselist=False)