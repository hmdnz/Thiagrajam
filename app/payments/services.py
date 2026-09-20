"""
app/payments/services.py

Business logic that ties provider calls to DB writes.
Routers stay thin and call into here.
"""

import json
import logging
from datetime import date, datetime, timezone
from typing import Optional, Tuple, List

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.bookings import models as booking_models
from app.payments import models as payment_models, utils
from app.payments import config as payment_config
from app.payments.schemas import PayoutCreateIn

logger = logging.getLogger(__name__)


# ============================================================
# WALLET HELPERS
# ============================================================

def get_or_create_wallet(db: Session, user_id: int) -> payment_models.Wallet:
    wallet = (
        db.query(payment_models.Wallet)
        .filter(payment_models.Wallet.user_id == user_id)
        .first()
    )
    if not wallet:
        wallet = payment_models.Wallet(user_id=user_id)
        db.add(wallet)
        db.flush()
    return wallet


def recompute_wallet_from_ledger(
    db: Session, user_id: int
) -> payment_models.Wallet:
    """
    Recalculate a wallet's balances from the ledger.
    Use when in doubt — the ledger is the source of truth.
    """
    credits = (
        db.query(
            func.coalesce(func.sum(payment_models.Transaction.amount_kobo), 0)
        )
        .filter(
            payment_models.Transaction.user_id == user_id,
            payment_models.Transaction.direction == "credit",
        )
        .scalar()
    ) or 0

    debits = (
        db.query(
            func.coalesce(func.sum(payment_models.Transaction.amount_kobo), 0)
        )
        .filter(
            payment_models.Transaction.user_id == user_id,
            payment_models.Transaction.direction == "debit",
        )
        .scalar()
    ) or 0

    commission = (
        db.query(
            func.coalesce(func.sum(payment_models.Transaction.amount_kobo), 0)
        )
        .filter(
            payment_models.Transaction.user_id == user_id,
            payment_models.Transaction.transaction_type
            == payment_models.TransactionTypeEnum.commission,
        )
        .scalar()
    ) or 0

    tax = (
        db.query(
            func.coalesce(func.sum(payment_models.Transaction.amount_kobo), 0)
        )
        .filter(
            payment_models.Transaction.user_id == user_id,
            payment_models.Transaction.transaction_type
            == payment_models.TransactionTypeEnum.tax,
        )
        .scalar()
    ) or 0

    wallet = get_or_create_wallet(db, user_id)
    wallet.available_balance_kobo = int(credits) - int(debits)
    wallet.lifetime_credits_kobo = int(credits)
    wallet.lifetime_debits_kobo = int(debits)
    wallet.lifetime_commission_kobo = int(commission)
    wallet.lifetime_tax_kobo = int(tax)
    return wallet


def record_ledger_entry(
    db: Session,
    *,
    user_id: int,
    transaction_type: payment_models.TransactionTypeEnum,
    direction: str,  # "credit" | "debit"
    amount_kobo: int,
    description: Optional[str] = None,
    payment_id: Optional[int] = None,
    booking_id: Optional[int] = None,
    payout_id: Optional[int] = None,
    refund_id: Optional[int] = None,
    provider_ref: Optional[str] = None,
    transaction_date: Optional[date] = None,
) -> payment_models.Transaction:
    """
    Append one immutable ledger row and update the cached wallet.
    Does NOT commit.
    """
    if direction not in ("credit", "debit"):
        raise ValueError("direction must be 'credit' or 'debit'")
    if amount_kobo <= 0:
        raise ValueError("Ledger amount must be positive.")

    tx = payment_models.Transaction(
        user_id=user_id,
        payment_id=payment_id,
        booking_id=booking_id,
        payout_id=payout_id,
        refund_id=refund_id,
        transaction_type=transaction_type,
        direction=direction,
        amount_kobo=amount_kobo,
        description=description,
        provider_ref=provider_ref,
        transaction_date=transaction_date or date.today(),
    )
    db.add(tx)

    wallet = get_or_create_wallet(db, user_id)
    if direction == "credit":
        wallet.available_balance_kobo += amount_kobo
        wallet.lifetime_credits_kobo += amount_kobo
    else:
        wallet.available_balance_kobo -= amount_kobo
        wallet.lifetime_debits_kobo += amount_kobo

    if transaction_type == payment_models.TransactionTypeEnum.commission:
        wallet.lifetime_commission_kobo += amount_kobo
    if transaction_type == payment_models.TransactionTypeEnum.tax:
        wallet.lifetime_tax_kobo += amount_kobo

    db.flush()
    return tx


# ============================================================
# PAYMENT: INITIALIZE
# ============================================================

async def initialize_booking_payment(
    db: Session,
    *,
    user: models.User,
    booking_id: int,
    provider: payment_models.PaymentProviderEnum,
    callback_url: Optional[str] = None,
) -> payment_models.Payment:

    booking = (
        db.query(booking_models.Booking)
        .filter(
            booking_models.Booking.id == booking_id,
            booking_models.Booking.passenger_id == user.id,
        )
        .first()
    )
    if not booking:
        raise HTTPException(404, "Booking not found.")

    if booking.status == booking_models.BookingStatusEnum.cancelled:
        raise HTTPException(400, "Cannot pay for a cancelled booking.")

    # Block double-charge
    already_paid = (
        db.query(payment_models.Payment)
        .filter(
            payment_models.Payment.booking_id == booking.id,
            payment_models.Payment.status
            == payment_models.PaymentStatusEnum.success,
        )
        .first()
    )
    if already_paid:
        raise HTTPException(400, "This booking has already been paid for.")

    # Reuse an existing pending payment (avoid duplicate refs)
    existing_pending = (
        db.query(payment_models.Payment)
        .filter(
            payment_models.Payment.booking_id == booking.id,
            payment_models.Payment.status
            == payment_models.PaymentStatusEnum.pending,
        )
        .order_by(payment_models.Payment.created_at.desc())
        .first()
    )

    amount_kobo = utils.naira_to_kobo(float(booking.fare))

    if existing_pending:
        payment = existing_pending
        # If provider changed, update the record
        if payment.provider != provider:
            payment.provider = provider
    else:
        transaction_ref = utils.generate_payment_ref(user.id)
        payment = payment_models.Payment(
            user_id=user.id,
            booking_id=booking.id,
            purpose=payment_models.PaymentPurposeEnum.booking,
            provider=provider,
            transaction_ref=transaction_ref,
            amount_kobo=amount_kobo,
            currency=payment_config.DEFAULT_CURRENCY,
            status=payment_models.PaymentStatusEnum.pending,
        )
        db.add(payment)
        db.flush()

    try:
        if provider == payment_models.PaymentProviderEnum.squad:
            resp = await utils.squad_initialize_payment(
                email=user.email,
                amount_kobo=amount_kobo,
                transaction_ref=payment.transaction_ref,
                callback_url=callback_url,
            )
            data = resp.get("data") or {}
            payment.auth_url = data.get("auth_url")
            payment.provider_ref = (
                data.get("transaction_ref") or payment.transaction_ref
            )
        else:
            resp = await utils.paystack_initialize_payment(
                email=user.email,
                amount_kobo=amount_kobo,
                reference=payment.transaction_ref,
                callback_url=callback_url,
                metadata={"booking_id": booking.id, "user_id": user.id},
            )
            data = resp.get("data") or {}
            payment.auth_url = data.get("authorization_url")
            payment.provider_ref = (
                data.get("reference") or payment.transaction_ref
            )

        payment.provider_response = json.dumps(resp)

    except Exception as exc:
        logger.exception("Payment initialize failed: %s", exc)
        payment.status = payment_models.PaymentStatusEnum.failed
        payment.failure_reason = str(exc)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Payment provider error: {exc}",
        )

    db.commit()
    db.refresh(payment)
    return payment


# ============================================================
# PAYMENT: VERIFY & SETTLE
# ============================================================

async def verify_and_settle_payment(
    db: Session,
    *,
    transaction_ref: str,
) -> payment_models.Payment:
    """
    Verify a payment with its stored provider and, on success,
    post the ledger entries (passenger credit + driver credit,
    net of commission and tax).

    Idempotent: safe to call from both /verify and webhook.
    Provider is read from the stored Payment row.
    """

    payment = (
        db.query(payment_models.Payment)
        .filter(payment_models.Payment.transaction_ref == transaction_ref)
        .first()
    )
    if not payment:
        raise HTTPException(404, "Payment not found.")

    if payment.status == payment_models.PaymentStatusEnum.success:
        return payment  # already settled

    try:
        if payment.provider == payment_models.PaymentProviderEnum.squad:
            resp = await utils.squad_verify_payment(payment.transaction_ref)
            data = resp.get("data") or {}
            raw_status = (data.get("transaction_status") or "").lower()
            amount_kobo = int(data.get("amount") or 0)
            merchant_amount_kobo = int(data.get("merchant_amount") or 0)
        else:
            resp = await utils.paystack_verify_payment(payment.transaction_ref)
            data = resp.get("data") or {}
            raw_status = (data.get("status") or "").lower()
            amount_kobo = int(data.get("amount") or 0)
            merchant_amount_kobo = 0
    except Exception as exc:
        logger.exception("Payment verify failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Payment verification failed: {exc}",
        )

    mapped = payment_config.map_provider_status(raw_status)
    payment.raw_status = raw_status
    payment.provider_response = json.dumps(resp)

    if mapped == "SUCCESS":
        payment.status = payment_models.PaymentStatusEnum.success
        payment.amount_kobo = amount_kobo or payment.amount_kobo
        payment.merchant_amount_kobo = merchant_amount_kobo or None
        payment.paid_at = datetime.now(timezone.utc)

        # --- Ledger: passenger paid ---
        record_ledger_entry(
            db,
            user_id=payment.user_id,
            transaction_type=payment_models.TransactionTypeEnum.payment,
            direction="credit",
            amount_kobo=payment.amount_kobo,
            description=f"Booking payment {payment.transaction_ref}",
            payment_id=payment.id,
            booking_id=payment.booking_id,
            provider_ref=payment.transaction_ref,
        )

        # --- Ledger: driver earns (gross credit + commission + tax debits) ---
        if payment.booking_id:
            booking = (
                db.query(booking_models.Booking)
                .filter(booking_models.Booking.id == payment.booking_id)
                .first()
            )
            if booking and booking.ride:
                breakdown = utils.compute_payout_breakdown(payment.amount_kobo)

                record_ledger_entry(
                    db,
                    user_id=booking.ride.driver_id,
                    transaction_type=payment_models.TransactionTypeEnum.payment,
                    direction="credit",
                    amount_kobo=payment.amount_kobo,
                    description=f"Earnings for booking {booking.id}",
                    payment_id=payment.id,
                    booking_id=booking.id,
                )

                if breakdown["commission_kobo"] > 0:
                    record_ledger_entry(
                        db,
                        user_id=booking.ride.driver_id,
                        transaction_type=payment_models.TransactionTypeEnum.commission,
                        direction="debit",
                        amount_kobo=breakdown["commission_kobo"],
                        description="Platform commission",
                        booking_id=booking.id,
                    )

                if breakdown["tax_kobo"] > 0:
                    record_ledger_entry(
                        db,
                        user_id=booking.ride.driver_id,
                        transaction_type=payment_models.TransactionTypeEnum.tax,
                        direction="debit",
                        amount_kobo=breakdown["tax_kobo"],
                        description="Withholding tax",
                        booking_id=booking.id,
                    )

                if booking.status == booking_models.BookingStatusEnum.pending:
                    booking.status = booking_models.BookingStatusEnum.confirmed

    elif mapped == "PENDING":
        payment.status = payment_models.PaymentStatusEnum.pending

    else:
        payment.status = payment_models.PaymentStatusEnum.failed
        payment.failure_reason = (
            data.get("message") or raw_status or "Payment failed"
        )

    db.commit()
    db.refresh(payment)
    return payment


# ============================================================
# REFUND FLOW
# ============================================================

def request_refund(
    db: Session,
    *,
    user: models.User,
    payment_id: int,
    reason: str,
    is_partial: bool,
    amount_kobo: Optional[int],
) -> payment_models.Refund:

    payment = (
        db.query(payment_models.Payment)
        .filter(
            payment_models.Payment.id == payment_id,
            payment_models.Payment.user_id == user.id,
        )
        .first()
    )
    if not payment:
        raise HTTPException(404, "Payment not found.")
    if payment.status != payment_models.PaymentStatusEnum.success:
        raise HTTPException(400, "Only successful payments can be refunded.")

    # Guard: previous refund already processed? Keep it simple:
    existing = (
        db.query(payment_models.Refund)
        .filter(
            payment_models.Refund.payment_id == payment.id,
            payment_models.Refund.status.in_(
                [
                    payment_models.RefundStatusEnum.pending,
                    payment_models.RefundStatusEnum.approved,
                    payment_models.RefundStatusEnum.processed,
                ]
            ),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            400,
            "A refund is already in progress or completed for this payment.",
        )

    refund_amount = amount_kobo if is_partial else payment.amount_kobo
    if not refund_amount or refund_amount <= 0:
        raise HTTPException(400, "Invalid refund amount.")
    if refund_amount > payment.amount_kobo:
        raise HTTPException(400, "Refund exceeds original payment amount.")

    refund = payment_models.Refund(
        payment_id=payment.id,
        booking_id=payment.booking_id,
        requested_by_id=user.id,
        refund_ref=utils.generate_refund_ref(
            payment.booking_id or payment.id
        ),
        is_partial=is_partial,
        amount_kobo=refund_amount,
        reason=reason,
        status=payment_models.RefundStatusEnum.pending,
    )
    db.add(refund)
    db.commit()
    db.refresh(refund)
    return refund


async def process_refund(
    db: Session,
    *,
    refund: payment_models.Refund,
    admin_user: models.User,
) -> payment_models.Refund:
    if refund.status != payment_models.RefundStatusEnum.pending:
        raise HTTPException(400, "Refund is not in pending state.")

    payment = refund.payment

    try:
        if payment.provider == payment_models.PaymentProviderEnum.squad:
            resp = await utils.squad_refund_payment(
                transaction_ref=payment.transaction_ref,
                reason=refund.reason,
                partial_amount_kobo=(
                    refund.amount_kobo if refund.is_partial else None
                ),
            )
            data = resp.get("data") or {}
            refund.provider_refund_ref = data.get("refund_ref")
            raw_status = (data.get("status") or "").lower()
        else:
            resp = await utils.paystack_refund_payment(
                transaction_ref=payment.transaction_ref,
                amount_kobo=(
                    refund.amount_kobo if refund.is_partial else None
                ),
                note=refund.reason,
            )
            data = resp.get("data") or {}
            refund.provider_refund_ref = str(data.get("id") or "")
            raw_status = (data.get("status") or "").lower()

        refund.raw_status = raw_status
        mapped = payment_config.map_provider_status(raw_status)
        if mapped == "SUCCESS":
            refund.status = payment_models.RefundStatusEnum.processed
        elif mapped == "PENDING":
            refund.status = payment_models.RefundStatusEnum.approved
        else:
            refund.status = payment_models.RefundStatusEnum.failed

    except Exception as exc:
        logger.exception("Refund provider call failed: %s", exc)
        refund.status = payment_models.RefundStatusEnum.failed
        refund.raw_status = str(exc)

    refund.reviewed_by_id = admin_user.id
    refund.processed_at = datetime.now(timezone.utc)

    # Only post ledger reversal on terminal-success states.
    if refund.status in (
        payment_models.RefundStatusEnum.approved,
        payment_models.RefundStatusEnum.processed,
    ):
        # Passenger debit
        record_ledger_entry(
            db,
            user_id=payment.user_id,
            transaction_type=payment_models.TransactionTypeEnum.refund,
            direction="debit",
            amount_kobo=refund.amount_kobo,
            description=f"Refund for payment {payment.transaction_ref}",
            payment_id=payment.id,
            booking_id=refund.booking_id,
            refund_id=refund.id,
        )

        # Driver reversal (only if payment was originally settled)
        if refund.booking_id:
            booking = (
                db.query(booking_models.Booking)
                .filter(booking_models.Booking.id == refund.booking_id)
                .first()
            )
            if booking and booking.ride:
                record_ledger_entry(
                    db,
                    user_id=booking.ride.driver_id,
                    transaction_type=payment_models.TransactionTypeEnum.refund,
                    direction="debit",
                    amount_kobo=refund.amount_kobo,
                    description=f"Reversal for booking {booking.id}",
                    booking_id=booking.id,
                    refund_id=refund.id,
                )

    db.commit()
    db.refresh(refund)
    return refund


# ============================================================
# PAYOUT FLOW
# ============================================================

def request_payout(
    db: Session,
    *,
    driver: models.User,
    payload: PayoutCreateIn,
) -> payment_models.Payout:

    if payload.amount_kobo > payment_config.MAX_PAYOUT_KOBO:
        raise HTTPException(
            400,
            f"Single payout cannot exceed "
            f"{utils.kobo_to_naira(payment_config.MAX_PAYOUT_KOBO)} NGN.",
        )

    wallet = get_or_create_wallet(db, driver.id)
    if payload.amount_kobo > wallet.available_balance_kobo:
        raise HTTPException(
            400,
            f"Insufficient balance. Available: "
            f"{utils.kobo_to_naira(wallet.available_balance_kobo)} NGN.",
        )

    breakdown = utils.compute_payout_breakdown(payload.amount_kobo)

    payout = payment_models.Payout(
        driver_id=driver.id,
        payout_ref=utils.generate_payout_ref(driver.id),
        provider=payload.provider,
        gross_amount_kobo=payload.amount_kobo,
        commission_kobo=breakdown["commission_kobo"],
        tax_kobo=breakdown["tax_kobo"],
        net_amount_kobo=breakdown["net_amount_kobo"],
        bank_code=payload.bank_code,
        account_number=payload.account_number,
        account_name=payload.account_name,
        status=payment_models.PayoutStatusEnum.pending,
    )
    db.add(payout)

    # Move money from available -> pending immediately.
    wallet.available_balance_kobo -= payload.amount_kobo
    wallet.pending_balance_kobo += payload.amount_kobo

    db.commit()
    db.refresh(payout)
    return payout


async def process_payout(
    db: Session,
    *,
    payout: payment_models.Payout,
    admin_user: models.User,
) -> payment_models.Payout:
    if payout.status != payment_models.PayoutStatusEnum.pending:
        raise HTTPException(400, "Payout is not pending.")

    try:
        if payout.provider == payment_models.PaymentProviderEnum.squad:
            resp = await utils.squad_transfer(
                transaction_ref=payout.payout_ref,
                amount_kobo=payout.net_amount_kobo,
                bank_code=payout.bank_code,
                account_number=payout.account_number,
                account_name=payout.account_name,
                remark="Ride earnings payout",
            )
            data = resp.get("data") or {}
            payout.provider_ref = data.get("transaction_ref")
            raw_status = (data.get("status") or "").lower()

        else:
            recipient_resp = await utils.paystack_create_transfer_recipient(
                name=payout.account_name,
                account_number=payout.account_number,
                bank_code=payout.bank_code,
            )
            recipient_code = (recipient_resp.get("data") or {}).get(
                "recipient_code"
            )
            payout.recipient_code = recipient_code

            resp = await utils.paystack_initiate_transfer(
                amount_kobo=payout.net_amount_kobo,
                recipient_code=recipient_code,
                reason="Ride earnings payout",
                reference=payout.payout_ref,
            )
            data = resp.get("data") or {}
            payout.provider_ref = (
                data.get("transfer_code") or data.get("reference")
            )
            raw_status = (data.get("status") or "").lower()

        payout.raw_status = raw_status
        mapped = payment_config.map_provider_status(raw_status)
        if mapped == "SUCCESS":
            payout.status = payment_models.PayoutStatusEnum.success
        elif mapped == "PENDING":
            payout.status = payment_models.PayoutStatusEnum.processing
        else:
            payout.status = payment_models.PayoutStatusEnum.failed

    except Exception as exc:
        logger.exception("Payout provider call failed: %s", exc)
        payout.status = payment_models.PayoutStatusEnum.failed
        payout.failure_reason = str(exc)

    payout.admin_note = (
        f"Reviewed by admin #{admin_user.id}" if admin_user else None
    )
    payout.processed_at = datetime.now(timezone.utc)

    wallet = get_or_create_wallet(db, payout.driver_id)

    if payout.status == payment_models.PayoutStatusEnum.success:
        # pending -> out
        wallet.pending_balance_kobo -= payout.gross_amount_kobo

        # Ledger entries: net debit, commission debit, tax debit
        record_ledger_entry(
            db,
            user_id=payout.driver_id,
            transaction_type=payment_models.TransactionTypeEnum.payout,
            direction="debit",
            amount_kobo=payout.net_amount_kobo,
            description=f"Payout {payout.payout_ref}",
            payout_id=payout.id,
            provider_ref=payout.provider_ref,
        )
        if payout.commission_kobo > 0:
            record_ledger_entry(
                db,
                user_id=payout.driver_id,
                transaction_type=payment_models.TransactionTypeEnum.commission,
                direction="debit",
                amount_kobo=payout.commission_kobo,
                description="Commission on payout",
                payout_id=payout.id,
            )
        if payout.tax_kobo > 0:
            record_ledger_entry(
                db,
                user_id=payout.driver_id,
                transaction_type=payment_models.TransactionTypeEnum.tax,
                direction="debit",
                amount_kobo=payout.tax_kobo,
                description="Tax on payout",
                payout_id=payout.id,
            )

    elif payout.status in (
        payment_models.PayoutStatusEnum.failed,
        payment_models.PayoutStatusEnum.reversed,
    ):
        # Return funds to available
        wallet.pending_balance_kobo -= payout.gross_amount_kobo
        wallet.available_balance_kobo += payout.gross_amount_kobo

    # "processing" -> leave pending balance as-is

    db.commit()
    db.refresh(payout)
    return payout


# ============================================================
# STATEMENT GENERATION
# ============================================================

def generate_statement(
    db: Session,
    *,
    user_id: int,
    period_start: date,
    period_end: date,
) -> Tuple[payment_models.Statement, List[payment_models.Transaction]]:

    if period_end < period_start:
        raise HTTPException(400, "period_end must be after period_start.")

    prior_credits = (
        db.query(
            func.coalesce(func.sum(payment_models.Transaction.amount_kobo), 0)
        )
        .filter(
            payment_models.Transaction.user_id == user_id,
            payment_models.Transaction.direction == "credit",
            payment_models.Transaction.transaction_date < period_start,
        )
        .scalar()
    ) or 0

    prior_debits = (
        db.query(
            func.coalesce(func.sum(payment_models.Transaction.amount_kobo), 0)
        )
        .filter(
            payment_models.Transaction.user_id == user_id,
            payment_models.Transaction.direction == "debit",
            payment_models.Transaction.transaction_date < period_start,
        )
        .scalar()
    ) or 0

    opening = int(prior_credits) - int(prior_debits)

    txns = (
        db.query(payment_models.Transaction)
        .filter(
            payment_models.Transaction.user_id == user_id,
            payment_models.Transaction.transaction_date >= period_start,
            payment_models.Transaction.transaction_date <= period_end,
        )
        .order_by(payment_models.Transaction.transaction_date.asc())
        .all()
    )

    total_credits = sum(
        t.amount_kobo for t in txns if t.direction == "credit"
    )
    total_debits = sum(
        t.amount_kobo for t in txns if t.direction == "debit"
    )
    total_commission = sum(
        t.amount_kobo
        for t in txns
        if t.transaction_type
        == payment_models.TransactionTypeEnum.commission
    )
    total_tax = sum(
        t.amount_kobo
        for t in txns
        if t.transaction_type == payment_models.TransactionTypeEnum.tax
    )
    closing = opening + total_credits - total_debits

    statement = payment_models.Statement(
        user_id=user_id,
        period_start=period_start,
        period_end=period_end,
        opening_balance_kobo=opening,
        closing_balance_kobo=closing,
        total_credits_kobo=total_credits,
        total_debits_kobo=total_debits,
        total_commission_kobo=total_commission,
        total_tax_kobo=total_tax,
        status=payment_models.StatementStatusEnum.issued,
    )
    db.add(statement)
    db.commit()
    db.refresh(statement)
    return statement, txns