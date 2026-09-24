"""
app/payments/schemas.py
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from app.payments.models import (
    PaymentProviderEnum,
    PaymentStatusEnum,
    PaymentPurposeEnum,
    TransactionTypeEnum,
    RefundStatusEnum,
    PayoutStatusEnum,
    StatementStatusEnum,
)


# ============================================================
# PAYMENT
# ============================================================

class PaymentInitializeIn(BaseModel):
    booking_id: int
    provider: PaymentProviderEnum = PaymentProviderEnum.squad
    callback_url: Optional[str] = None


class PaymentInitializeOut(BaseModel):
    payment_id: int
    transaction_ref: str
    amount_kobo: int
    amount_naira: Decimal
    currency: str
    provider: PaymentProviderEnum
    auth_url: Optional[str] = None
    status: PaymentStatusEnum


class PaymentVerifyIn(BaseModel):
    transaction_ref: str


class PaymentOut(BaseModel):
    id: int
    user_id: UUID
    booking_id: Optional[int] = None
    purpose: PaymentPurposeEnum
    provider: PaymentProviderEnum
    transaction_ref: str
    provider_ref: Optional[str] = None
    amount_kobo: int
    amount_naira: Decimal
    merchant_amount_kobo: Optional[int] = None
    currency: str
    status: PaymentStatusEnum
    raw_status: Optional[str] = None
    failure_reason: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# REFUND
# ============================================================

class RefundCreateIn(BaseModel):
    payment_id: int
    reason: str = Field(..., min_length=3, max_length=500)
    is_partial: bool = False
    amount_kobo: Optional[int] = Field(default=None, gt=0)


class RefundAdminReviewIn(BaseModel):
    approve: bool
    admin_note: Optional[str] = None


class RefundOut(BaseModel):
    id: int
    payment_id: int
    booking_id: Optional[int] = None
    refund_ref: str
    provider_refund_ref: Optional[str] = None
    is_partial: bool
    amount_kobo: int
    amount_naira: Decimal
    currency: str
    reason: str
    status: RefundStatusEnum
    raw_status: Optional[str] = None
    admin_note: Optional[str] = None
    processed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# PAYOUT
# ============================================================

class PayoutCreateIn(BaseModel):
    amount_kobo: int = Field(..., gt=0)
    provider: PaymentProviderEnum = PaymentProviderEnum.squad
    bank_code: str
    account_number: str
    account_name: str


class PayoutAdminReviewIn(BaseModel):
    approve: bool
    admin_note: Optional[str] = None


class PayoutOut(BaseModel):
    id: int
    driver_id: UUID
    payout_ref: str
    provider_ref: Optional[str] = None
    gross_amount_kobo: int
    commission_kobo: int
    tax_kobo: int
    net_amount_kobo: int
    currency: str
    bank_code: str
    bank_name: Optional[str] = None
    account_number: str
    account_name: str
    recipient_code: Optional[str] = None
    status: str
    raw_status: Optional[str] = None
    failure_reason: Optional[str] = None
    admin_note: Optional[str] = None
    processed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# TRANSACTION
# ============================================================

class TransactionOut(BaseModel):
    id: int
    user_id: UUID
    payment_id: Optional[int] = None
    booking_id: Optional[int] = None
    payout_id: Optional[int] = None
    refund_id: Optional[int] = None
    transaction_type: TransactionTypeEnum
    direction: str
    amount_kobo: int
    amount_naira: Decimal
    currency: str
    description: Optional[str] = None
    provider_ref: Optional[str] = None
    transaction_date: date
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# WALLET
# ============================================================

class WalletOut(BaseModel):
    id: int
    user_id: UUID
    available_balance_kobo: int
    pending_balance_kobo: int
    lifetime_credits_kobo: int
    lifetime_debits_kobo: int
    lifetime_commission_kobo: int
    lifetime_tax_kobo: int
    available_balance_naira: Decimal
    pending_balance_naira: Decimal
    lifetime_credits_naira: Decimal
    lifetime_debits_naira: Decimal
    lifetime_commission_naira: Decimal
    lifetime_tax_naira: Decimal
    currency: str
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# STATEMENT
# ============================================================

class StatementGenerateIn(BaseModel):
    period_start: date
    period_end: date


class StatementOut(BaseModel):
    id: int
    user_id: UUID
    period_start: date
    period_end: date
    opening_balance_kobo: int
    closing_balance_kobo: int
    total_credits_kobo: int
    total_debits_kobo: int
    total_commission_kobo: int
    total_tax_kobo: int
    opening_balance_naira: Decimal
    closing_balance_naira: Decimal
    total_credits_naira: Decimal
    total_debits_naira: Decimal
    total_commission_naira: Decimal
    total_tax_naira: Decimal
    currency: str
    status: StatementStatusEnum
    generated_at: datetime
    transactions: List[TransactionOut] = []

    model_config = ConfigDict(from_attributes=True)