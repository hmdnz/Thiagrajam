
"""Business logic for payments, wallet ledgers, refunds, payouts, and statements.

Payout status changes and their ledger consequences must go through
finalize_payout_status(). Provider webhooks/admin routes should not mutate wallet
balances directly.
"""

import json
import logging
from datetime import date, datetime, timezone
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.bookings import models as booking_models
from app.payments import config as payment_config
from app.payments import models as payment_models, utils
from app.payments.schemas import PayoutCreateIn

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _provider_error_detail(exc: Exception) -> str:
    """Include the provider response body in an error when available."""
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            body = response.text
        except Exception:
            body = ""
        if body:
            return f"{exc} | provider said: {body}"
    return str(exc)


def _transaction_exists_for_payment(
    db: Session,
    *,
    payment_id: int,
    user_id,
    transaction_type: payment_models.TransactionTypeEnum,
    direction: str,
    balance_bucket: Optional[payment_models.BalanceBucketEnum] = None,
) -> bool:
    """Check for an existing entry, optionally requiring the same bucket."""
    query = db.query(payment_models.Transaction.id).filter(
        payment_models.Transaction.payment_id == payment_id,
        payment_models.Transaction.user_id == user_id,
        payment_models.Transaction.transaction_type == transaction_type,
        payment_models.Transaction.direction == direction,
    )
    if balance_bucket is not None:
        query = query.filter(
            payment_models.Transaction.balance_bucket == balance_bucket
        )
    return query.first() is not None


def _get_payment_driver(
    db: Session,
    payment: payment_models.Payment,
):
    """Return ``(booking, driver_id)`` for a booking payment."""
    if not payment.booking_id:
        return None, None
    booking = (
        db.query(booking_models.Booking)
        .filter(booking_models.Booking.id == payment.booking_id)
        .first()
    )
    if not booking or not booking.ride:
        return booking, None
    return booking, booking.ride.driver_id


def _sum_transaction_amount(
    db: Session,
    *,
    user_id,
    transaction_type: payment_models.TransactionTypeEnum,
    direction: Optional[str] = None,
    balance_bucket: Optional[payment_models.BalanceBucketEnum] = None,
    payment_id: Optional[int] = None,
    payout_id: Optional[int] = None,
    refund_id: Optional[int] = None,
) -> int:
    query = db.query(
        func.coalesce(func.sum(payment_models.Transaction.amount_kobo), 0)
    ).filter(
        payment_models.Transaction.user_id == user_id,
        payment_models.Transaction.transaction_type == transaction_type,
    )
    if direction is not None:
        query = query.filter(payment_models.Transaction.direction == direction)
    if balance_bucket is not None:
        query = query.filter(
            payment_models.Transaction.balance_bucket == balance_bucket
        )
    if payment_id is not None:
        query = query.filter(payment_models.Transaction.payment_id == payment_id)
    if payout_id is not None:
        query = query.filter(payment_models.Transaction.payout_id == payout_id)
    if refund_id is not None:
        query = query.filter(payment_models.Transaction.refund_id == refund_id)
    return int(query.scalar() or 0)


def _payment_earnings_from_ledger(
    db: Session,
    *,
    payment_id: int,
    user_id,
) -> int:
    """Return net payment earnings, excluding internal settlement transfers.

    Excluding balance_transfer rows is essential for safe retry after a partial
    settlement: a previously recorded transfer debit must not reduce the
    original earnings amount used to complete its matching credit.
    """
    credits = (
        db.query(func.coalesce(func.sum(payment_models.Transaction.amount_kobo), 0))
        .filter(
            payment_models.Transaction.payment_id == payment_id,
            payment_models.Transaction.user_id == user_id,
            payment_models.Transaction.balance_bucket
            == payment_models.BalanceBucketEnum.pending_earnings,
            payment_models.Transaction.direction == "credit",
            payment_models.Transaction.transaction_type
            != payment_models.TransactionTypeEnum.balance_transfer,
        )
        .scalar()
        or 0
    )
    debits = (
        db.query(func.coalesce(func.sum(payment_models.Transaction.amount_kobo), 0))
        .filter(
            payment_models.Transaction.payment_id == payment_id,
            payment_models.Transaction.user_id == user_id,
            payment_models.Transaction.balance_bucket
            == payment_models.BalanceBucketEnum.pending_earnings,
            payment_models.Transaction.direction == "debit",
            payment_models.Transaction.transaction_type
            != payment_models.TransactionTypeEnum.balance_transfer,
        )
        .scalar()
        or 0
    )
    return int(credits) - int(debits)


# ---------------------------------------------------------------------------
# Wallet helpers and immutable ledger
# ---------------------------------------------------------------------------

def get_or_create_wallet(db: Session, user_id) -> payment_models.Wallet:
    wallet = (
        db.query(payment_models.Wallet)
        .filter(payment_models.Wallet.user_id == user_id)
        .first()
    )
    if wallet is None:
        wallet = payment_models.Wallet(
            user_id=user_id,
            available_balance_kobo=0,
            pending_balance_kobo=0,
            pending_earnings_balance_kobo=0,
            lifetime_credits_kobo=0,
            lifetime_debits_kobo=0,
            lifetime_commission_kobo=0,
            lifetime_tax_kobo=0,
        )
        db.add(wallet)
        db.flush()
    return wallet


def recompute_wallet_from_ledger(
    db: Session,
    user_id,
) -> payment_models.Wallet:
    """Rebuild cached wallet balances from the ledger source of truth."""
    def bucket_net(bucket: payment_models.BalanceBucketEnum) -> int:
        credits = (
            db.query(func.coalesce(func.sum(payment_models.Transaction.amount_kobo), 0))
            .filter(
                payment_models.Transaction.user_id == user_id,
                payment_models.Transaction.balance_bucket == bucket,
                payment_models.Transaction.direction == "credit",
            )
            .scalar()
            or 0
        )
        debits = (
            db.query(func.coalesce(func.sum(payment_models.Transaction.amount_kobo), 0))
            .filter(
                payment_models.Transaction.user_id == user_id,
                payment_models.Transaction.balance_bucket == bucket,
                payment_models.Transaction.direction == "debit",
            )
            .scalar()
            or 0
        )
        return int(credits) - int(debits)

    lifetime_credits = (
        db.query(func.coalesce(func.sum(payment_models.Transaction.amount_kobo), 0))
        .filter(
            payment_models.Transaction.user_id == user_id,
            payment_models.Transaction.direction == "credit",
            payment_models.Transaction.transaction_type
            != payment_models.TransactionTypeEnum.balance_transfer,
        )
        .scalar()
        or 0
    )
    lifetime_debits = (
        db.query(func.coalesce(func.sum(payment_models.Transaction.amount_kobo), 0))
        .filter(
            payment_models.Transaction.user_id == user_id,
            payment_models.Transaction.direction == "debit",
            payment_models.Transaction.transaction_type
            != payment_models.TransactionTypeEnum.balance_transfer,
        )
        .scalar()
        or 0
    )

    # Reversal entries are credits. Use debit-minus-credit for the net
    # commission/tax metrics so reversal credits reduce the original amount.
    commission_debits = _sum_transaction_amount(
        db,
        user_id=user_id,
        transaction_type=payment_models.TransactionTypeEnum.commission,
        direction="debit",
    )
    commission_credits = _sum_transaction_amount(
        db,
        user_id=user_id,
        transaction_type=payment_models.TransactionTypeEnum.commission,
        direction="credit",
    )
    tax_debits = _sum_transaction_amount(
        db,
        user_id=user_id,
        transaction_type=payment_models.TransactionTypeEnum.tax,
        direction="debit",
    )
    tax_credits = _sum_transaction_amount(
        db,
        user_id=user_id,
        transaction_type=payment_models.TransactionTypeEnum.tax,
        direction="credit",
    )

    wallet = get_or_create_wallet(db, user_id)
    wallet.available_balance_kobo = bucket_net(
        payment_models.BalanceBucketEnum.available
    )
    wallet.pending_earnings_balance_kobo = bucket_net(
        payment_models.BalanceBucketEnum.pending_earnings
    )
    wallet.pending_balance_kobo = bucket_net(
        payment_models.BalanceBucketEnum.pending_payout
    )
    wallet.lifetime_credits_kobo = int(lifetime_credits)
    wallet.lifetime_debits_kobo = int(lifetime_debits)
    wallet.lifetime_commission_kobo = commission_debits - commission_credits
    wallet.lifetime_tax_kobo = tax_debits - tax_credits
    return wallet


def record_ledger_entry(
    db: Session,
    *,
    user_id,
    transaction_type: payment_models.TransactionTypeEnum,
    direction: str,
    amount_kobo: int,
    balance_bucket: payment_models.BalanceBucketEnum,
    description: Optional[str] = None,
    payment_id: Optional[int] = None,
    booking_id: Optional[int] = None,
    payout_id: Optional[int] = None,
    refund_id: Optional[int] = None,
    provider_ref: Optional[str] = None,
    transaction_date: Optional[date] = None,
) -> payment_models.Transaction:
    """Append one ledger entry and update cached bucket/lifetime totals. Does not commit."""
    if direction not in ("credit", "debit"):
        raise ValueError("direction must be 'credit' or 'debit'")
    if not isinstance(amount_kobo, int) or isinstance(amount_kobo, bool) or amount_kobo <= 0:
        raise ValueError("Ledger amount must be a positive integer number of kobo.")

    tx = payment_models.Transaction(
        user_id=user_id,
        payment_id=payment_id,
        booking_id=booking_id,
        payout_id=payout_id,
        refund_id=refund_id,
        transaction_type=transaction_type,
        balance_bucket=balance_bucket,
        direction=direction,
        amount_kobo=amount_kobo,
        description=description,
        provider_ref=provider_ref,
        transaction_date=transaction_date or date.today(),
    )
    db.add(tx)
    wallet = get_or_create_wallet(db, user_id)

    if balance_bucket == payment_models.BalanceBucketEnum.available:
        if direction == "credit":
            wallet.available_balance_kobo += amount_kobo
        else:
            wallet.available_balance_kobo -= amount_kobo
    elif balance_bucket == payment_models.BalanceBucketEnum.pending_earnings:
        if direction == "credit":
            wallet.pending_earnings_balance_kobo += amount_kobo
        else:
            wallet.pending_earnings_balance_kobo -= amount_kobo
    elif balance_bucket == payment_models.BalanceBucketEnum.pending_payout:
        if direction == "credit":
            wallet.pending_balance_kobo += amount_kobo
        else:
            wallet.pending_balance_kobo -= amount_kobo
    else:
        raise ValueError(f"Unsupported balance bucket: {balance_bucket}")

    if transaction_type != payment_models.TransactionTypeEnum.balance_transfer:
        if direction == "credit":
            wallet.lifetime_credits_kobo += amount_kobo
        else:
            wallet.lifetime_debits_kobo += amount_kobo

        commission_delta = 0
        if transaction_type == payment_models.TransactionTypeEnum.commission:
            commission_delta = amount_kobo if direction == "debit" else -amount_kobo
        if commission_delta:
            wallet.lifetime_commission_kobo += commission_delta

        tax_delta = 0
        if transaction_type == payment_models.TransactionTypeEnum.tax:
            tax_delta = amount_kobo if direction == "debit" else -amount_kobo
        if tax_delta:
            wallet.lifetime_tax_kobo += tax_delta

    db.flush()
    return tx


# ---------------------------------------------------------------------------
# Payment initialization and verification
# ---------------------------------------------------------------------------

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
    if booking.status == booking_models.BookingStatusEnum.CANCELLED:
        raise HTTPException(400, "Cannot pay for a cancelled booking.")

    already_paid = (
        db.query(payment_models.Payment)
        .filter(
            payment_models.Payment.booking_id == booking.id,
            payment_models.Payment.status == payment_models.PaymentStatusEnum.success,
        )
        .first()
    )
    if already_paid:
        raise HTTPException(400, "This booking has already been paid for.")

    existing_pending = (
        db.query(payment_models.Payment)
        .filter(
            payment_models.Payment.booking_id == booking.id,
            payment_models.Payment.status == payment_models.PaymentStatusEnum.pending,
        )
        .order_by(payment_models.Payment.created_at.desc())
        .first()
    )
    amount_kobo = utils.naira_to_kobo(float(booking.fare))

    if existing_pending:
        payment = existing_pending
        if payment.provider != provider:
            payment.provider = provider
    else:
        payment = payment_models.Payment(
            user_id=user.id,
            booking_id=booking.id,
            purpose=payment_models.PaymentPurposeEnum.booking,
            provider=provider,
            transaction_ref=utils.generate_payment_ref(user.id),
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
            logger.info("Squad initialize response: %s", resp)
            inner = resp.get("data")
            data = inner if isinstance(inner, dict) else resp
            payment.auth_url = data.get("checkout_url") or data.get("auth_url")
            payment.provider_ref = data.get("transaction_ref") or payment.transaction_ref
            if not payment.auth_url:
                raise RuntimeError("Squad did not return a checkout URL.")
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
            payment.provider_ref = data.get("reference") or payment.transaction_ref
            if not payment.auth_url:
                raise RuntimeError("Paystack did not return an authorization URL.")
        payment.provider_response = json.dumps(resp)
    except Exception as exc:
        detail = _provider_error_detail(exc)
        logger.exception("Payment initialize failed: %s", detail)
        payment.status = payment_models.PaymentStatusEnum.failed
        payment.failure_reason = detail
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Payment provider error: {detail}",
        )

    db.commit()
    db.refresh(payment)
    return payment


async def verify_and_settle_payment(
    db: Session,
    *,
    transaction_ref: str,
) -> payment_models.Payment:
    """Verify a provider payment and record the resulting immutable ledger entries."""
    payment = (
        db.query(payment_models.Payment)
        .filter(payment_models.Payment.transaction_ref == transaction_ref)
        .with_for_update()
        .first()
    )
    if not payment:
        raise HTTPException(404, "Payment not found.")

    if payment.settlement_status == payment_models.SettlementStatusEnum.settled:
        return payment

    if payment.status == payment_models.PaymentStatusEnum.success:
        booking, _driver_id = _get_payment_driver(db, payment)
        if booking and booking.status == booking_models.BookingStatusEnum.TRIP_COMPLETED:
            _mark_payment_eligible_for_settlement(db, payment=payment)
            _settle_payment(db, payment=payment)
            db.commit()
            db.refresh(payment)
        return payment

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
        detail = _provider_error_detail(exc)
        logger.exception("Payment verify failed: %s", detail)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Payment verification failed: {detail}",
        )

    mapped = payment_config.map_provider_status(raw_status)
    payment.raw_status = raw_status
    payment.provider_response = json.dumps(resp)

    if mapped == "SUCCESS":
        if amount_kobo <= 0:
            raise HTTPException(400, "Payment provider returned an invalid amount.")
        if amount_kobo != payment.amount_kobo:
            raise HTTPException(
                400,
                f"Payment amount mismatch. Expected {payment.amount_kobo} kobo, provider returned {amount_kobo} kobo.",
            )

        payment.status = payment_models.PaymentStatusEnum.success
        payment.amount_kobo = amount_kobo
        payment.merchant_amount_kobo = merchant_amount_kobo or None
        payment.paid_at = datetime.now(timezone.utc)
        if payment.settlement_status != payment_models.SettlementStatusEnum.settled:
            payment.settlement_status = payment_models.SettlementStatusEnum.held

        # Passenger ledger entry. This mirrors the existing product ledger behavior;
        # if this is intended as a pure expense rather than a wallet top-up, the
        # customer-ledger semantics should be revisited separately.
        if not _transaction_exists_for_payment(
            db,
            payment_id=payment.id,
            user_id=payment.user_id,
            transaction_type=payment_models.TransactionTypeEnum.payment,
            direction="credit",
            balance_bucket=payment_models.BalanceBucketEnum.available,
        ):
            record_ledger_entry(
                db,
                user_id=payment.user_id,
                transaction_type=payment_models.TransactionTypeEnum.payment,
                direction="credit",
                amount_kobo=payment.amount_kobo,
                balance_bucket=payment_models.BalanceBucketEnum.available,
                description=f"Booking payment {payment.transaction_ref}",
                payment_id=payment.id,
                booking_id=payment.booking_id,
                provider_ref=payment.transaction_ref,
            )

        booking, driver_id = _get_payment_driver(db, payment)
        if booking and driver_id:
            gross_exists = _transaction_exists_for_payment(
                db,
                payment_id=payment.id,
                user_id=driver_id,
                transaction_type=payment_models.TransactionTypeEnum.payment,
                direction="credit",
                balance_bucket=payment_models.BalanceBucketEnum.pending_earnings,
            )
            breakdown = utils.compute_payout_breakdown(payment.amount_kobo)
            if not gross_exists:
                record_ledger_entry(
                    db,
                    user_id=driver_id,
                    transaction_type=payment_models.TransactionTypeEnum.payment,
                    direction="credit",
                    amount_kobo=payment.amount_kobo,
                    balance_bucket=payment_models.BalanceBucketEnum.pending_earnings,
                    description=f"Pending earnings for booking {booking.id}",
                    payment_id=payment.id,
                    booking_id=booking.id,
                )

            # Independently ensure commission and tax entries exist; a prior partial
            # transaction must not cause these entries to be skipped.
            for tx_type, amount, description in (
                (
                    payment_models.TransactionTypeEnum.commission,
                    breakdown["commission_kobo"],
                    "Platform commission",
                ),
                (
                    payment_models.TransactionTypeEnum.tax,
                    breakdown["tax_kobo"],
                    "Withholding tax",
                ),
            ):
                if amount <= 0:
                    continue
                exists = _transaction_exists_for_payment(
                    db,
                    payment_id=payment.id,
                    user_id=driver_id,
                    transaction_type=tx_type,
                    direction="debit",
                    balance_bucket=payment_models.BalanceBucketEnum.pending_earnings,
                )
                if not exists:
                    record_ledger_entry(
                        db,
                        user_id=driver_id,
                        transaction_type=tx_type,
                        direction="debit",
                        amount_kobo=amount,
                        balance_bucket=payment_models.BalanceBucketEnum.pending_earnings,
                        description=description,
                        payment_id=payment.id,
                        booking_id=booking.id,
                    )

            if booking.status == booking_models.BookingStatusEnum.PENDING:
                booking.status = booking_models.BookingStatusEnum.CONFIRMED
            if booking.status == booking_models.BookingStatusEnum.TRIP_COMPLETED:
                _mark_payment_eligible_for_settlement(db, payment=payment)
                _settle_payment(db, payment=payment)

    elif mapped == "PENDING":
        payment.status = payment_models.PaymentStatusEnum.pending
        if payment.settlement_status != payment_models.SettlementStatusEnum.settled:
            payment.settlement_status = payment_models.SettlementStatusEnum.held
    else:
        payment.status = payment_models.PaymentStatusEnum.failed
        payment.failure_reason = data.get("message") or raw_status or "Payment failed"
        if payment.settlement_status != payment_models.SettlementStatusEnum.settled:
            payment.settlement_status = payment_models.SettlementStatusEnum.held

    db.commit()
    db.refresh(payment)
    return payment


# ---------------------------------------------------------------------------
# Settlement
# ---------------------------------------------------------------------------

def _mark_payment_eligible_for_settlement(
    db: Session,
    *,
    payment: payment_models.Payment,
) -> payment_models.Payment:
    if payment.status != payment_models.PaymentStatusEnum.success:
        raise HTTPException(400, "Only successful payments can become eligible for settlement.")
    if payment.settlement_status == payment_models.SettlementStatusEnum.settled:
        return payment
    if payment.settlement_status == payment_models.SettlementStatusEnum.eligible_for_settlement:
        return payment

    booking, driver_id = _get_payment_driver(db, payment)
    if not booking or not driver_id:
        raise HTTPException(400, "Payment has no valid driver settlement target.")
    if booking.status != booking_models.BookingStatusEnum.TRIP_COMPLETED:
        raise HTTPException(400, "Payment is not yet eligible for settlement.")

    payment.settlement_status = payment_models.SettlementStatusEnum.eligible_for_settlement
    payment.settlement_eligible_at = datetime.now(timezone.utc)
    db.flush()
    return payment


def _settle_payment(
    db: Session,
    *,
    payment: payment_models.Payment,
) -> payment_models.Payment:
    """Move net pending earnings into available using paired internal transfers."""
    if payment.status != payment_models.PaymentStatusEnum.success:
        raise HTTPException(400, "Only successful payments can be settled.")
    if payment.settlement_status == payment_models.SettlementStatusEnum.settled:
        return payment
    if payment.settlement_status != payment_models.SettlementStatusEnum.eligible_for_settlement:
        raise HTTPException(400, "Payment is not eligible for settlement.")

    booking, driver_id = _get_payment_driver(db, payment)
    if not booking or not driver_id:
        raise HTTPException(400, "Payment has no valid driver settlement target.")

    wallet = get_or_create_wallet(db, driver_id)
    net_pending = _payment_earnings_from_ledger(
        db,
        payment_id=payment.id,
        user_id=driver_id,
    )
    if net_pending < 0:
        raise HTTPException(400, "Payment settlement amount cannot be negative.")

    debit_amount = _sum_transaction_amount(
        db,
        user_id=driver_id,
        transaction_type=payment_models.TransactionTypeEnum.balance_transfer,
        direction="debit",
        balance_bucket=payment_models.BalanceBucketEnum.pending_earnings,
        payment_id=payment.id,
    )
    credit_amount = _sum_transaction_amount(
        db,
        user_id=driver_id,
        transaction_type=payment_models.TransactionTypeEnum.balance_transfer,
        direction="credit",
        balance_bucket=payment_models.BalanceBucketEnum.available,
        payment_id=payment.id,
    )
    if debit_amount not in (0, net_pending) or credit_amount not in (0, net_pending):
        raise HTTPException(409, "Existing settlement transfer amount is inconsistent.")

    if not debit_amount and net_pending:
        if net_pending > wallet.pending_earnings_balance_kobo:
            raise HTTPException(400, "Pending earnings balance is insufficient for settlement.")
        record_ledger_entry(
            db,
            user_id=driver_id,
            transaction_type=payment_models.TransactionTypeEnum.balance_transfer,
            direction="debit",
            amount_kobo=net_pending,
            balance_bucket=payment_models.BalanceBucketEnum.pending_earnings,
            description=f"Settlement transfer for payment {payment.transaction_ref}",
            payment_id=payment.id,
            booking_id=payment.booking_id,
        )
    if not credit_amount and net_pending:
        record_ledger_entry(
            db,
            user_id=driver_id,
            transaction_type=payment_models.TransactionTypeEnum.balance_transfer,
            direction="credit",
            amount_kobo=net_pending,
            balance_bucket=payment_models.BalanceBucketEnum.available,
            description=f"Settlement available balance for payment {payment.transaction_ref}",
            payment_id=payment.id,
            booking_id=payment.booking_id,
        )

    payment.settlement_amount_kobo = net_pending
    payment.settlement_status = payment_models.SettlementStatusEnum.settled
    payment.settled_at = datetime.now(timezone.utc)
    db.flush()
    return payment


def mark_payment_eligible_for_settlement(
    db: Session,
    *,
    payment_id: int,
) -> payment_models.Payment:
    payment = db.query(payment_models.Payment).filter(
        payment_models.Payment.id == payment_id
    ).with_for_update().first()
    if not payment:
        raise HTTPException(404, "Payment not found.")
    try:
        _mark_payment_eligible_for_settlement(db, payment=payment)
        db.commit()
        db.refresh(payment)
        return payment
    except Exception:
        db.rollback()
        raise


def settle_payment(
    db: Session,
    *,
    payment_id: int,
) -> payment_models.Payment:
    payment = db.query(payment_models.Payment).filter(
        payment_models.Payment.id == payment_id
    ).with_for_update().first()
    if not payment:
        raise HTTPException(404, "Payment not found.")
    try:
        _settle_payment(db, payment=payment)
        db.commit()
        db.refresh(payment)
        return payment
    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------------------------
# Refunds
# ---------------------------------------------------------------------------

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
        .with_for_update()
        .first()
    )
    if not payment:
        raise HTTPException(404, "Payment not found.")
    if payment.status != payment_models.PaymentStatusEnum.success:
        raise HTTPException(400, "Only successful payments can be refunded.")

    refunded_total = (
        db.query(func.coalesce(func.sum(payment_models.Refund.amount_kobo), 0))
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
        .scalar()
        or 0
    )
    refund_amount = amount_kobo if is_partial else payment.amount_kobo
    if not refund_amount or refund_amount <= 0:
        raise HTTPException(400, "Invalid refund amount.")
    if int(refunded_total) + refund_amount > payment.amount_kobo:
        raise HTTPException(400, "Cumulative refunds exceed original payment amount.")

    refund = payment_models.Refund(
        payment_id=payment.id,
        booking_id=payment.booking_id,
        requested_by_id=user.id,
        refund_ref=utils.generate_refund_ref(payment.booking_id or payment.id),
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
    refund = (
        db.query(payment_models.Refund)
        .filter(payment_models.Refund.id == refund.id)
        .with_for_update()
        .first()
    )
    if not refund:
        raise HTTPException(404, "Refund not found.")
    if refund.status != payment_models.RefundStatusEnum.pending:
        raise HTTPException(400, "Refund is not in pending state.")

    payment = refund.payment
    try:
        if payment.provider == payment_models.PaymentProviderEnum.squad:
            resp = await utils.squad_refund_payment(
                transaction_ref=payment.transaction_ref,
                reason=refund.reason,
                partial_amount=refund.amount_kobo if refund.is_partial else None,
            )
            data = resp.get("data") or {}
            refund.provider_refund_ref = data.get("refund_ref")
            raw_status = (data.get("status") or "").lower()
        else:
            resp = await utils.paystack_refund_payment(
                transaction_ref=payment.transaction_ref,
                amount_kobo=refund.amount_kobo if refund.is_partial else None,
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
        detail = _provider_error_detail(exc)
        logger.exception("Refund provider call failed: %s", detail)
        refund.status = payment_models.RefundStatusEnum.failed
        refund.raw_status = detail

    refund.reviewed_by_id = admin_user.id
    refund.processed_at = datetime.now(timezone.utc)

    if refund.status == payment_models.RefundStatusEnum.processed:
        passenger_exists = (
            db.query(payment_models.Transaction.id)
            .filter(
                payment_models.Transaction.refund_id == refund.id,
                payment_models.Transaction.user_id == payment.user_id,
                payment_models.Transaction.transaction_type == payment_models.TransactionTypeEnum.refund,
                payment_models.Transaction.direction == "debit",
                payment_models.Transaction.balance_bucket == payment_models.BalanceBucketEnum.available,
            )
            .first()
            is not None
        )
        if not passenger_exists:
            record_ledger_entry(
                db,
                user_id=payment.user_id,
                transaction_type=payment_models.TransactionTypeEnum.refund,
                direction="debit",
                amount_kobo=refund.amount_kobo,
                balance_bucket=payment_models.BalanceBucketEnum.available,
                description=f"Refund for payment {payment.transaction_ref}",
                payment_id=payment.id,
                booking_id=refund.booking_id,
                refund_id=refund.id,
            )

        booking, driver_id = _get_payment_driver(db, payment)
        if booking and driver_id:
            bucket = (
                payment_models.BalanceBucketEnum.available
                if payment.settlement_status == payment_models.SettlementStatusEnum.settled
                else payment_models.BalanceBucketEnum.pending_earnings
            )
            exists = (
                db.query(payment_models.Transaction.id)
                .filter(
                    payment_models.Transaction.refund_id == refund.id,
                    payment_models.Transaction.user_id == driver_id,
                    payment_models.Transaction.transaction_type == payment_models.TransactionTypeEnum.refund,
                    payment_models.Transaction.direction == "debit",
                    payment_models.Transaction.balance_bucket == bucket,
                )
                .first()
                is not None
            )
            if not exists:
                breakdown = utils.compute_payout_breakdown(refund.amount_kobo)
                driver_reversal = (
                    refund.amount_kobo
                    - breakdown["commission_kobo"]
                    - breakdown["tax_kobo"]
                )
                if driver_reversal > 0:
                    driver_wallet = get_or_create_wallet(db, driver_id)
                    # A provider-confirmed refund must not be lost merely because
                    # the driver's spendable bucket is short. Posting the debit may
                    # make this bucket negative, representing a recoverable balance.
                    record_ledger_entry(
                        db,
                        user_id=driver_id,
                        transaction_type=payment_models.TransactionTypeEnum.refund,
                        direction="debit",
                        amount_kobo=driver_reversal,
                        balance_bucket=bucket,
                        description=f"Refund reversal for booking {booking.id}",
                        payment_id=payment.id,
                        booking_id=booking.id,
                        refund_id=refund.id,
                    )

    try:
        db.commit()
        db.refresh(refund)
        return refund
    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------------------------
# Payouts
# ---------------------------------------------------------------------------

def request_payout(
    db: Session,
    *,
    driver: models.User,
    payload: PayoutCreateIn,
) -> payment_models.Payout:
    if payload.amount_kobo <= 0:
        raise HTTPException(400, "Payout amount must be greater than zero.")
    if payload.amount_kobo > payment_config.MAX_PAYOUT_KOBO:
        raise HTTPException(
            400,
            f"Single payout cannot exceed {utils.kobo_to_naira(payment_config.MAX_PAYOUT_KOBO)} NGN.",
        )

    wallet = (
        db.query(payment_models.Wallet)
        .filter(payment_models.Wallet.user_id == driver.id)
        .with_for_update()
        .first()
    )
    if wallet is None:
        wallet = get_or_create_wallet(db, driver.id)
    if payload.amount_kobo > wallet.available_balance_kobo:
        raise HTTPException(
            400,
            f"Insufficient balance. Available: {utils.kobo_to_naira(wallet.available_balance_kobo)} NGN.",
        )

    breakdown = utils.compute_payout_breakdown(payload.amount_kobo)
    if (
        breakdown["net_amount_kobo"]
        + breakdown["commission_kobo"]
        + breakdown["tax_kobo"]
        != payload.amount_kobo
    ):
        raise HTTPException(400, "Payout breakdown does not equal gross payout amount.")

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
    db.flush()

    try:
        record_ledger_entry(
            db,
            user_id=driver.id,
            transaction_type=payment_models.TransactionTypeEnum.balance_transfer,
            direction="debit",
            amount_kobo=payout.gross_amount_kobo,
            balance_bucket=payment_models.BalanceBucketEnum.available,
            description=f"Payout reservation {payout.payout_ref}",
            payout_id=payout.id,
        )
        record_ledger_entry(
            db,
            user_id=driver.id,
            transaction_type=payment_models.TransactionTypeEnum.balance_transfer,
            direction="credit",
            amount_kobo=payout.gross_amount_kobo,
            balance_bucket=payment_models.BalanceBucketEnum.pending_payout,
            description=f"Pending payout reservation {payout.payout_ref}",
            payout_id=payout.id,
        )
        db.commit()
        db.refresh(payout)
        return payout
    except Exception:
        db.rollback()
        raise


def _payout_ledger_total(
    db: Session,
    *,
    payout: payment_models.Payout,
    transaction_type: payment_models.TransactionTypeEnum,
    direction: str,
    balance_bucket: payment_models.BalanceBucketEnum,
) -> int:
    """Amount recorded for one payout/type/direction/bucket combination."""
    return _sum_transaction_amount(
        db,
        user_id=payout.driver_id,
        transaction_type=transaction_type,
        direction=direction,
        balance_bucket=balance_bucket,
        payout_id=payout.id,
    )


def _payout_has_success_debits(
    db: Session,
    *,
    payout: payment_models.Payout,
) -> bool:
    return (
        db.query(payment_models.Transaction.id)
        .filter(
            payment_models.Transaction.payout_id == payout.id,
            payment_models.Transaction.user_id == payout.driver_id,
            payment_models.Transaction.transaction_type.in_(
                [
                    payment_models.TransactionTypeEnum.payout,
                    payment_models.TransactionTypeEnum.commission,
                    payment_models.TransactionTypeEnum.tax,
                ]
            ),
            payment_models.Transaction.direction == "debit",
            payment_models.Transaction.balance_bucket
            == payment_models.BalanceBucketEnum.pending_payout,
        )
        .first()
        is not None
    )


def _post_successful_payout_ledger(
    db: Session,
    *,
    payout: payment_models.Payout,
) -> None:
    """Consume the payout reserve using net payout, commission and tax debits."""
    if (
        payout.net_amount_kobo
        + payout.commission_kobo
        + payout.tax_kobo
        != payout.gross_amount_kobo
    ):
        raise HTTPException(400, "Payout breakdown does not equal gross payout amount.")

    reserve_credit = _payout_ledger_total(
        db,
        payout=payout,
        transaction_type=payment_models.TransactionTypeEnum.balance_transfer,
        direction="credit",
        balance_bucket=payment_models.BalanceBucketEnum.pending_payout,
    )
    reserve_release_debit = _payout_ledger_total(
        db,
        payout=payout,
        transaction_type=payment_models.TransactionTypeEnum.balance_transfer,
        direction="debit",
        balance_bucket=payment_models.BalanceBucketEnum.pending_payout,
    )
    if reserve_credit != payout.gross_amount_kobo:
        raise HTTPException(409, "Payout reserve is missing or has an incorrect amount.")
    if reserve_release_debit:
        raise HTTPException(409, "Cannot mark payout successful after its reserve was released.")

    entries = (
        (payment_models.TransactionTypeEnum.payout, payout.net_amount_kobo, f"Payout {payout.payout_ref}"),
        (payment_models.TransactionTypeEnum.commission, payout.commission_kobo, "Commission on payout"),
        (payment_models.TransactionTypeEnum.tax, payout.tax_kobo, "Tax on payout"),
    )
    missing = []
    for tx_type, expected_amount, description in entries:
        if expected_amount <= 0:
            continue
        debit_total = _payout_ledger_total(
            db,
            payout=payout,
            transaction_type=tx_type,
            direction="debit",
            balance_bucket=payment_models.BalanceBucketEnum.pending_payout,
        )
        credit_total = _payout_ledger_total(
            db,
            payout=payout,
            transaction_type=tx_type,
            direction="credit",
            balance_bucket=payment_models.BalanceBucketEnum.pending_payout,
        )
        if debit_total not in (0, expected_amount) or credit_total not in (0, expected_amount):
            raise HTTPException(409, f"Existing {tx_type.value} payout entries have inconsistent amounts.")
        if debit_total == 0:
            missing.append((tx_type, expected_amount, description))

    wallet = get_or_create_wallet(db, payout.driver_id)
    missing_total = sum(amount for _, amount, _ in missing)
    if missing_total > wallet.pending_balance_kobo:
        raise HTTPException(400, "Pending payout balance is insufficient.")

    for tx_type, amount, description in missing:
        record_ledger_entry(
            db,
            user_id=payout.driver_id,
            transaction_type=tx_type,
            direction="debit",
            amount_kobo=amount,
            balance_bucket=payment_models.BalanceBucketEnum.pending_payout,
            description=description,
            payout_id=payout.id,
            provider_ref=payout.provider_ref,
        )


def _reverse_successful_payout_entries(
    db: Session,
    *,
    payout: payment_models.Payout,
) -> None:
    """Credit back any successful net/commission/tax debits before releasing reserve."""
    for tx_type, description in (
        (payment_models.TransactionTypeEnum.payout, "Reverse payout payment"),
        (payment_models.TransactionTypeEnum.commission, "Reverse payout commission"),
        (payment_models.TransactionTypeEnum.tax, "Reverse payout tax"),
    ):
        debit_amount = _payout_ledger_total(
            db,
            payout=payout,
            transaction_type=tx_type,
            direction="debit",
            balance_bucket=payment_models.BalanceBucketEnum.pending_payout,
        )
        credit_amount = _payout_ledger_total(
            db,
            payout=payout,
            transaction_type=tx_type,
            direction="credit",
            balance_bucket=payment_models.BalanceBucketEnum.pending_payout,
        )
        if credit_amount > debit_amount:
            raise HTTPException(409, "Payout reversal credits exceed the original debit.")
        amount = debit_amount - credit_amount
        if amount > 0:
            record_ledger_entry(
                db,
                user_id=payout.driver_id,
                transaction_type=tx_type,
                direction="credit",
                amount_kobo=amount,
                balance_bucket=payment_models.BalanceBucketEnum.pending_payout,
                description=description,
                payout_id=payout.id,
                provider_ref=payout.provider_ref,
            )


def _release_payout_reserve(
    db: Session,
    *,
    payout: payment_models.Payout,
) -> None:
    """Return the reserved gross amount to available, safely retryable."""
    gross = payout.gross_amount_kobo
    wallet = get_or_create_wallet(db, payout.driver_id)

    reserve_credit = _payout_ledger_total(
        db,
        payout=payout,
        transaction_type=payment_models.TransactionTypeEnum.balance_transfer,
        direction="credit",
        balance_bucket=payment_models.BalanceBucketEnum.pending_payout,
    )
    reserve_debit = _payout_ledger_total(
        db,
        payout=payout,
        transaction_type=payment_models.TransactionTypeEnum.balance_transfer,
        direction="debit",
        balance_bucket=payment_models.BalanceBucketEnum.pending_payout,
    )
    available_credit = _payout_ledger_total(
        db,
        payout=payout,
        transaction_type=payment_models.TransactionTypeEnum.balance_transfer,
        direction="credit",
        balance_bucket=payment_models.BalanceBucketEnum.available,
    )
    if reserve_credit != gross:
        raise HTTPException(409, "Payout reserve is missing or has an incorrect amount.")
    if reserve_debit not in (0, gross) or available_credit not in (0, gross):
        raise HTTPException(409, "Payout reserve-release ledger amounts are inconsistent.")

    if reserve_debit == 0:
        if gross > wallet.pending_balance_kobo:
            raise HTTPException(400, "Pending payout balance is insufficient for release.")
        record_ledger_entry(
            db,
            user_id=payout.driver_id,
            transaction_type=payment_models.TransactionTypeEnum.balance_transfer,
            direction="debit",
            amount_kobo=gross,
            balance_bucket=payment_models.BalanceBucketEnum.pending_payout,
            description=f"Release payout reserve {payout.payout_ref}",
            payout_id=payout.id,
            provider_ref=payout.provider_ref,
        )
    if available_credit == 0:
        record_ledger_entry(
            db,
            user_id=payout.driver_id,
            transaction_type=payment_models.TransactionTypeEnum.balance_transfer,
            direction="credit",
            amount_kobo=gross,
            balance_bucket=payment_models.BalanceBucketEnum.available,
            description=f"Return payout funds {payout.payout_ref}",
            payout_id=payout.id,
            provider_ref=payout.provider_ref,
        )


def finalize_payout_status(
    db: Session,
    *,
    payout: payment_models.Payout,
    target_status: payment_models.PayoutStatusEnum,
    raw_status: Optional[str] = None,
    provider_ref: Optional[str] = None,
    failure_reason: Optional[str] = None,
    admin_user: Optional[models.User] = None,
    admin_note: Optional[str] = None,
) -> payment_models.Payout:
    """Atomically apply a payout status transition and its ledger effects.

    Call this service from provider webhooks and admin rejection. The payout row
    is locked before inspecting current state to reduce duplicate/racing postings.
    """
    allowed = {
        payment_models.PayoutStatusEnum.processing,
        payment_models.PayoutStatusEnum.success,
        payment_models.PayoutStatusEnum.failed,
        payment_models.PayoutStatusEnum.reversed,
    }
    if target_status not in allowed:
        raise HTTPException(400, "Unsupported payout status transition.")

    try:
        locked = (
            db.query(payment_models.Payout)
            .filter(payment_models.Payout.id == payout.id)
            .with_for_update()
            .populate_existing()
            .first()
        )


        if not locked:
            raise HTTPException(404, "Payout not found.")
        payout = locked
        current = payout.status
        terminal = {
            payment_models.PayoutStatusEnum.success,
            payment_models.PayoutStatusEnum.failed,
            payment_models.PayoutStatusEnum.reversed,
        }

        # A terminal state must not be moved backwards by a stale event.
        if current == payment_models.PayoutStatusEnum.reversed and target_status != current:
            return payout
        if current == payment_models.PayoutStatusEnum.success and target_status in {
            payment_models.PayoutStatusEnum.processing,
            payment_models.PayoutStatusEnum.failed,
        }:
            return payout
        if current == payment_models.PayoutStatusEnum.failed and target_status in {
            payment_models.PayoutStatusEnum.processing,
            payment_models.PayoutStatusEnum.success,
        }:
            return payout
        if current in terminal and target_status == payment_models.PayoutStatusEnum.processing:
            return payout

        if target_status == payment_models.PayoutStatusEnum.success:
            _post_successful_payout_ledger(db, payout=payout)
        elif target_status == payment_models.PayoutStatusEnum.failed:
            if _payout_has_success_debits(db, payout=payout):
                raise HTTPException(
                    409,
                    "Payout has successful ledger debits; use REVERSED for a returned transfer.",
                )
            _release_payout_reserve(db, payout=payout)
        elif target_status == payment_models.PayoutStatusEnum.reversed:
            _reverse_successful_payout_entries(db, payout=payout)
            _release_payout_reserve(db, payout=payout)
        # PROCESSING deliberately leaves the reserve untouched.

        payout.status = target_status
        if raw_status is not None:
            payout.raw_status = raw_status
        if provider_ref is not None:
            payout.provider_ref = provider_ref
        if failure_reason is not None:
            payout.failure_reason = failure_reason
        if admin_note is not None:
            payout.admin_note = admin_note
        elif admin_user is not None:
            payout.admin_note = f"Reviewed by admin #{admin_user.id}"
        payout.processed_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(payout)
        return payout
    except Exception:
        db.rollback()
        raise


async def process_payout(
    db: Session,
    *,
    payout: payment_models.Payout,
    admin_user: models.User,
) -> payment_models.Payout:
    """Initiate a provider transfer; final ledger posting is centralized."""
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
            provider_ref = data.get("transaction_ref")
            raw_status = (data.get("status") or data.get("transaction_status") or "").lower()
        else:
            recipient_resp = await utils.paystack_create_transfer_recipient(
                name=payout.account_name,
                account_number=payout.account_number,
                bank_code=payout.bank_code,
            )
            recipient_code = (recipient_resp.get("data") or {}).get("recipient_code")
            if not recipient_code:
                raise RuntimeError("Paystack did not return a transfer recipient code.")
            payout.recipient_code = recipient_code
            resp = await utils.paystack_initiate_transfer(
                amount_kobo=payout.net_amount_kobo,
                recipient_code=recipient_code,
                reason="Ride earnings payout",
                reference=payout.payout_ref,
            )
            data = resp.get("data") or {}
            provider_ref = data.get("transfer_code") or data.get("reference")
            raw_status = (data.get("status") or "").lower()
    except Exception as exc:
        detail = _provider_error_detail(exc)
        logger.exception("Payout provider call failed: %s", detail)
        # A timeout does not prove the provider rejected the transfer. Do not release
        # the funds until a verified webhook/reconciliation reports a terminal result.
        return finalize_payout_status(
            db,
            payout=payout,
            target_status=payment_models.PayoutStatusEnum.processing,
            raw_status="initiation_outcome_unknown",
            failure_reason=detail,
            admin_user=admin_user,
        )

    mapped = payment_config.map_provider_status(raw_status)
    if mapped == "SUCCESS":
        target = payment_models.PayoutStatusEnum.success
        failure_reason = None
    elif mapped == "FAILED":
        target = payment_models.PayoutStatusEnum.failed
        failure_reason = data.get("message") or raw_status or "Payout failed"
    else:
        target = payment_models.PayoutStatusEnum.processing
        failure_reason = None

    return finalize_payout_status(
        db,
        payout=payout,
        target_status=target,
        raw_status=raw_status or "unknown",
        provider_ref=provider_ref,
        failure_reason=failure_reason,
        admin_user=admin_user,
    )


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------

def generate_statement(
    db: Session,
    *,
    user_id,
    period_start: date,
    period_end: date,
) -> Tuple[payment_models.Statement, List[payment_models.Transaction]]:
    if period_end < period_start:
        raise HTTPException(400, "period_end must be after period_start.")

    financial_type_filter = (
        payment_models.Transaction.transaction_type
        != payment_models.TransactionTypeEnum.balance_transfer
    )
    prior_credits = (
        db.query(func.coalesce(func.sum(payment_models.Transaction.amount_kobo), 0))
        .filter(
            payment_models.Transaction.user_id == user_id,
            payment_models.Transaction.direction == "credit",
            payment_models.Transaction.transaction_date < period_start,
            financial_type_filter,
        )
        .scalar()
        or 0
    )
    prior_debits = (
        db.query(func.coalesce(func.sum(payment_models.Transaction.amount_kobo), 0))
        .filter(
            payment_models.Transaction.user_id == user_id,
            payment_models.Transaction.direction == "debit",
            payment_models.Transaction.transaction_date < period_start,
            financial_type_filter,
        )
        .scalar()
        or 0
    )
    opening = int(prior_credits) - int(prior_debits)

    txns = (
        db.query(payment_models.Transaction)
        .filter(
            payment_models.Transaction.user_id == user_id,
            payment_models.Transaction.transaction_date >= period_start,
            payment_models.Transaction.transaction_date <= period_end,
            financial_type_filter,
        )
        .order_by(payment_models.Transaction.transaction_date.asc())
        .all()
    )
    total_credits = sum(t.amount_kobo for t in txns if t.direction == "credit")
    total_debits = sum(t.amount_kobo for t in txns if t.direction == "debit")
    total_commission = sum(
        t.amount_kobo if t.direction == "debit" else -t.amount_kobo
        for t in txns
        if t.transaction_type == payment_models.TransactionTypeEnum.commission
    )
    total_tax = sum(
        t.amount_kobo if t.direction == "debit" else -t.amount_kobo
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
