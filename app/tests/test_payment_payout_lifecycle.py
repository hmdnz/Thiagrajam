"""Focused tests for Wenyfour payout finalization and wallet reconciliation.

Copy this file to app/tests/test_payment_payout_lifecycle.py.
These tests intentionally do not use the existing test_user fixture because
that fixture currently passes the read-only User.profile_complete property.
"""

import uuid

import pytest

from app import models
from app.payments import models as payment_models
from app.payments import services as payment_services


STARTING_AVAILABLE_KOBO = 5_000
GROSS_KOBO = 1_000
NET_KOBO = 800
COMMISSION_KOBO = 150
TAX_KOBO = 50


def _create_driver(db_session):
    """Create a minimal user without assigning the profile_complete property."""
    suffix = uuid.uuid4().hex
    driver = models.User(
        id=uuid.uuid4(),
        email=f"payout-test-{suffix}@example.com",
        phone_number=f"{uuid.uuid4().int % 10**11:011d}",
        password="test-only-password-hash",
        role="passenger",
    )
    db_session.add(driver)
    db_session.flush()
    return driver


def _create_reserved_payout(db_session):
    """Seed funds, create a payout, and ledger AVAILABLE -> PENDING_PAYOUT."""
    driver = _create_driver(db_session)

    payment_services.record_ledger_entry(
        db_session,
        user_id=driver.id,
        transaction_type=payment_models.TransactionTypeEnum.adjustment,
        direction="credit",
        amount_kobo=STARTING_AVAILABLE_KOBO,
        balance_bucket=payment_models.BalanceBucketEnum.available,
        description="Test opening funds",
    )

    payout = payment_models.Payout(
        driver_id=driver.id,
        payout_ref=f"TEST-PAYOUT-{uuid.uuid4().hex}",
        provider=payment_models.PaymentProviderEnum.paystack,
        gross_amount_kobo=GROSS_KOBO,
        commission_kobo=COMMISSION_KOBO,
        tax_kobo=TAX_KOBO,
        net_amount_kobo=NET_KOBO,
        bank_code="044",
        account_number="0123456789",
        account_name="Test Driver",
        status=payment_models.PayoutStatusEnum.pending,
    )
    db_session.add(payout)
    db_session.flush()

    payment_services.record_ledger_entry(
        db_session,
        user_id=driver.id,
        transaction_type=payment_models.TransactionTypeEnum.balance_transfer,
        direction="debit",
        amount_kobo=GROSS_KOBO,
        balance_bucket=payment_models.BalanceBucketEnum.available,
        description=f"Test reserve {payout.payout_ref}",
        payout_id=payout.id,
    )
    payment_services.record_ledger_entry(
        db_session,
        user_id=driver.id,
        transaction_type=payment_models.TransactionTypeEnum.balance_transfer,
        direction="credit",
        amount_kobo=GROSS_KOBO,
        balance_bucket=payment_models.BalanceBucketEnum.pending_payout,
        description=f"Test pending reserve {payout.payout_ref}",
        payout_id=payout.id,
    )

    db_session.commit()
    db_session.refresh(payout)
    return driver, payout


def _wallet(db_session, user_id):
    wallet = (
        db_session.query(payment_models.Wallet)
        .filter(payment_models.Wallet.user_id == user_id)
        .one()
    )
    db_session.refresh(wallet)
    return wallet


def _transaction_count(
    db_session,
    *,
    payout_id,
    transaction_type,
    direction,
    bucket=payment_models.BalanceBucketEnum.pending_payout,
):
    return (
        db_session.query(payment_models.Transaction)
        .filter(
            payment_models.Transaction.payout_id == payout_id,
            payment_models.Transaction.transaction_type == transaction_type,
            payment_models.Transaction.direction == direction,
            payment_models.Transaction.balance_bucket == bucket,
        )
        .count()
    )


def test_successful_payout_consumes_reserve_once(db_session):
    driver, payout = _create_reserved_payout(db_session)

    payment_services.finalize_payout_status(
        db_session,
        payout=payout,
        target_status=payment_models.PayoutStatusEnum.success,
        raw_status="success",
    )

    wallet = _wallet(db_session, driver.id)
    assert payout.status == payment_models.PayoutStatusEnum.success
    assert wallet.available_balance_kobo == STARTING_AVAILABLE_KOBO - GROSS_KOBO
    assert wallet.pending_balance_kobo == 0

    assert _transaction_count(
        db_session,
        payout_id=payout.id,
        transaction_type=payment_models.TransactionTypeEnum.payout,
        direction="debit",
    ) == 1
    assert _transaction_count(
        db_session,
        payout_id=payout.id,
        transaction_type=payment_models.TransactionTypeEnum.commission,
        direction="debit",
    ) == 1
    assert _transaction_count(
        db_session,
        payout_id=payout.id,
        transaction_type=payment_models.TransactionTypeEnum.tax,
        direction="debit",
    ) == 1

    # Simulate a duplicate success webhook: ledger postings must not repeat.
    payment_services.finalize_payout_status(
        db_session,
        payout=payout,
        target_status=payment_models.PayoutStatusEnum.success,
        raw_status="success",
    )

    wallet = _wallet(db_session, driver.id)
    assert wallet.available_balance_kobo == STARTING_AVAILABLE_KOBO - GROSS_KOBO
    assert wallet.pending_balance_kobo == 0
    assert _transaction_count(
        db_session,
        payout_id=payout.id,
        transaction_type=payment_models.TransactionTypeEnum.payout,
        direction="debit",
    ) == 1


def test_failed_payout_returns_reserve_once(db_session):
    driver, payout = _create_reserved_payout(db_session)

    payment_services.finalize_payout_status(
        db_session,
        payout=payout,
        target_status=payment_models.PayoutStatusEnum.failed,
        raw_status="failed",
        failure_reason="Test provider failure",
    )

    wallet = _wallet(db_session, driver.id)
    assert payout.status == payment_models.PayoutStatusEnum.failed
    assert wallet.available_balance_kobo == STARTING_AVAILABLE_KOBO
    assert wallet.pending_balance_kobo == 0

    # Duplicate failure notification must not release the same reserve twice.
    payment_services.finalize_payout_status(
        db_session,
        payout=payout,
        target_status=payment_models.PayoutStatusEnum.failed,
        raw_status="failed",
    )

    wallet = _wallet(db_session, driver.id)
    assert wallet.available_balance_kobo == STARTING_AVAILABLE_KOBO
    assert wallet.pending_balance_kobo == 0
    assert _transaction_count(
        db_session,
        payout_id=payout.id,
        transaction_type=payment_models.TransactionTypeEnum.balance_transfer,
        direction="debit",
    ) == 1
    assert _transaction_count(
        db_session,
        payout_id=payout.id,
        transaction_type=payment_models.TransactionTypeEnum.balance_transfer,
        direction="credit",
        bucket=payment_models.BalanceBucketEnum.available,
    ) == 1


def test_reversal_after_success_restores_available_and_nets_fees(db_session):
    driver, payout = _create_reserved_payout(db_session)

    payment_services.finalize_payout_status(
        db_session,
        payout=payout,
        target_status=payment_models.PayoutStatusEnum.success,
        raw_status="success",
    )
    payment_services.finalize_payout_status(
        db_session,
        payout=payout,
        target_status=payment_models.PayoutStatusEnum.reversed,
        raw_status="reversed",
    )

    wallet = payment_services.recompute_wallet_from_ledger(
        db_session,
        driver.id,
    )
    db_session.commit()
    db_session.refresh(wallet)

    assert payout.status == payment_models.PayoutStatusEnum.reversed
    assert wallet.available_balance_kobo == STARTING_AVAILABLE_KOBO
    assert wallet.pending_balance_kobo == 0
    assert wallet.lifetime_commission_kobo == 0
    assert wallet.lifetime_tax_kobo == 0

    # A repeated reversal event must not issue another release.
    transaction_count_before = (
        db_session.query(payment_models.Transaction)
        .filter(payment_models.Transaction.payout_id == payout.id)
        .count()
    )
    payment_services.finalize_payout_status(
        db_session,
        payout=payout,
        target_status=payment_models.PayoutStatusEnum.reversed,
        raw_status="reversed",
    )
    transaction_count_after = (
        db_session.query(payment_models.Transaction)
        .filter(payment_models.Transaction.payout_id == payout.id)
        .count()
    )
    assert transaction_count_after == transaction_count_before


def test_stale_failed_event_does_not_undo_success(db_session):
    driver, payout = _create_reserved_payout(db_session)

    payment_services.finalize_payout_status(
        db_session,
        payout=payout,
        target_status=payment_models.PayoutStatusEnum.success,
        raw_status="success",
    )
    payment_services.finalize_payout_status(
        db_session,
        payout=payout,
        target_status=payment_models.PayoutStatusEnum.failed,
        raw_status="late-failure-event",
    )

    db_session.refresh(payout)
    wallet = _wallet(db_session, driver.id)
    assert payout.status == payment_models.PayoutStatusEnum.success
    assert wallet.available_balance_kobo == STARTING_AVAILABLE_KOBO - GROSS_KOBO
    assert wallet.pending_balance_kobo == 0
