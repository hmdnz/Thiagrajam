"""
app/payments/routers.py
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Request,
)
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime, timezone
import json
import logging

from app import models, oauth2
from app.database import get_db
from app.payments import (
    models as payment_models,
    schemas as payment_schemas,
    services as payment_services,
    utils as payment_utils,
)

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/payments", tags=["Payments"])


# ============================================================
# SERIALIZERS (add *_naira convenience fields)
# ============================================================

def _payment_out(p: payment_models.Payment) -> dict:
    return {
        "id": p.id,
        "user_id": p.user_id,
        "booking_id": p.booking_id,
        "purpose": p.purpose,
        "provider": p.provider,
        "transaction_ref": p.transaction_ref,
        "provider_ref": p.provider_ref,
        "amount_kobo": p.amount_kobo,
        "amount_naira": payment_utils.kobo_to_naira(p.amount_kobo),
        "merchant_amount_kobo": p.merchant_amount_kobo,
        "currency": p.currency,
        "status": p.status,
        "raw_status": p.raw_status,
        "failure_reason": p.failure_reason,
        "paid_at": p.paid_at,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _refund_out(r: payment_models.Refund) -> dict:
    return {
        "id": r.id,
        "payment_id": r.payment_id,
        "booking_id": r.booking_id,
        "refund_ref": r.refund_ref,
        "provider_refund_ref": r.provider_refund_ref,
        "is_partial": r.is_partial,
        "amount_kobo": r.amount_kobo,
        "amount_naira": payment_utils.kobo_to_naira(r.amount_kobo),
        "currency": r.currency,
        "reason": r.reason,
        "status": r.status,
        "raw_status": r.raw_status,
        "admin_note": r.admin_note,
        "processed_at": r.processed_at,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def _payout_out(p: payment_models.Payout) -> dict:
    return {
        "id": p.id,
        "driver_id": p.driver_id,
        "payout_ref": p.payout_ref,
        "provider_ref": p.provider_ref,
        "provider": p.provider,
        "gross_amount_kobo": p.gross_amount_kobo,
        "commission_kobo": p.commission_kobo,
        "tax_kobo": p.tax_kobo,
        "net_amount_kobo": p.net_amount_kobo,
        "gross_amount_naira": payment_utils.kobo_to_naira(p.gross_amount_kobo),
        "commission_naira": payment_utils.kobo_to_naira(p.commission_kobo),
        "tax_naira": payment_utils.kobo_to_naira(p.tax_kobo),
        "net_amount_naira": payment_utils.kobo_to_naira(p.net_amount_kobo),
        "currency": p.currency,
        "bank_code": p.bank_code,
        "bank_name": p.bank_name,
        "account_number": p.account_number,
        "account_name": p.account_name,
        "status": p.status,
        "raw_status": p.raw_status,
        "failure_reason": p.failure_reason,
        "admin_note": p.admin_note,
        "processed_at": p.processed_at,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _transaction_out(t: payment_models.Transaction) -> dict:
    return {
        "id": t.id,
        "user_id": t.user_id,
        "payment_id": t.payment_id,
        "booking_id": t.booking_id,
        "payout_id": t.payout_id,
        "refund_id": t.refund_id,
        "transaction_type": t.transaction_type,
        "direction": t.direction,
        "amount_kobo": t.amount_kobo,
        "amount_naira": payment_utils.kobo_to_naira(t.amount_kobo),
        "currency": t.currency,
        "description": t.description,
        "provider_ref": t.provider_ref,
        "transaction_date": t.transaction_date,
        "created_at": t.created_at,
    }


def _wallet_out(w: payment_models.Wallet) -> dict:
    return {
        "id": w.id,
        "user_id": w.user_id,
        "available_balance_kobo": w.available_balance_kobo,
        "pending_balance_kobo": w.pending_balance_kobo,
        "lifetime_credits_kobo": w.lifetime_credits_kobo,
        "lifetime_debits_kobo": w.lifetime_debits_kobo,
        "lifetime_commission_kobo": w.lifetime_commission_kobo,
        "lifetime_tax_kobo": w.lifetime_tax_kobo,
        "available_balance_naira": payment_utils.kobo_to_naira(
            w.available_balance_kobo
        ),
        "pending_balance_naira": payment_utils.kobo_to_naira(
            w.pending_balance_kobo
        ),
        "lifetime_credits_naira": payment_utils.kobo_to_naira(
            w.lifetime_credits_kobo
        ),
        "lifetime_debits_naira": payment_utils.kobo_to_naira(
            w.lifetime_debits_kobo
        ),
        "lifetime_commission_naira": payment_utils.kobo_to_naira(
            w.lifetime_commission_kobo
        ),
        "lifetime_tax_naira": payment_utils.kobo_to_naira(
            w.lifetime_tax_kobo
        ),
        "currency": w.currency,
        "updated_at": w.updated_at,
    }


def _statement_out(
    s: payment_models.Statement,
    txns: Optional[List[payment_models.Transaction]] = None,
) -> dict:
    return {
        "id": s.id,
        "user_id": s.user_id,
        "period_start": s.period_start,
        "period_end": s.period_end,
        "opening_balance_kobo": s.opening_balance_kobo,
        "closing_balance_kobo": s.closing_balance_kobo,
        "total_credits_kobo": s.total_credits_kobo,
        "total_debits_kobo": s.total_debits_kobo,
        "total_commission_kobo": s.total_commission_kobo,
        "total_tax_kobo": s.total_tax_kobo,
        "opening_balance_naira": payment_utils.kobo_to_naira(
            s.opening_balance_kobo
        ),
        "closing_balance_naira": payment_utils.kobo_to_naira(
            s.closing_balance_kobo
        ),
        "total_credits_naira": payment_utils.kobo_to_naira(
            s.total_credits_kobo
        ),
        "total_debits_naira": payment_utils.kobo_to_naira(
            s.total_debits_kobo
        ),
        "total_commission_naira": payment_utils.kobo_to_naira(
            s.total_commission_kobo
        ),
        "total_tax_naira": payment_utils.kobo_to_naira(s.total_tax_kobo),
        "currency": s.currency,
        "status": s.status,
        "generated_at": s.generated_at,
        "transactions": [
            _transaction_out(t) for t in (txns or [])
        ],
    }


# ============================================================
# PAYMENT: INITIALIZE
# POST /payments/initialize
# ============================================================


@router.post(
    "/initialize",
    response_model=payment_schemas.PaymentInitializeOut,
    status_code=status.HTTP_201_CREATED,
)
async def initialize_payment(
    payload: payment_schemas.PaymentInitializeIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    if not current_user.can_book_rides:
        raise HTTPException(
            403, "Profile complete and verified NIN required to pay."
        )

    payment = await payment_services.initialize_booking_payment(
        db,
        user=current_user,
        booking_id=payload.booking_id,
        provider=payload.provider,
        callback_url=payload.callback_url,
    )

    return payment_schemas.PaymentInitializeOut(
        payment_id=payment.id,
        transaction_ref=payment.transaction_ref,
        amount_kobo=payment.amount_kobo,
        amount_naira=payment_utils.kobo_to_naira(payment.amount_kobo),
        currency=payment.currency,
        provider=payment.provider,
        auth_url=payment.auth_url,
        status=payment.status,
    )


# ============================================================
# PAYMENT: VERIFY
# POST /payments/verify
# ============================================================

@router.post(
    "/verify",
    response_model=payment_schemas.PaymentOut,
)
async def verify_payment(
    payload: payment_schemas.PaymentVerifyIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    payment = await payment_services.verify_and_settle_payment(
        db, transaction_ref=payload.transaction_ref
    )

    if payment.user_id != current_user.id and not current_user.is_admin:
        # Do not leak which refs belong to whom
        raise HTTPException(403, "Not allowed.")

    return _payment_out(payment)


# ============================================================
# PAYMENT: WEBHOOKS
# ============================================================

@router.post("/webhook/squad")
async def squad_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    signature = request.headers.get("x-squad-encrypted-body", "")

    if not payment_utils.verify_squad_webhook(raw_body, signature):
        logger.warning("Invalid Squad webhook signature.")
        raise HTTPException(401, "Invalid signature.")

    try:
        payload = json.loads(raw_body)
    except Exception:
        raise HTTPException(400, "Invalid JSON.")

    event = payload.get("Event")
    transaction_ref = payload.get("TransactionRef")

    if event in ("charge_successful", "charge_failed") and transaction_ref:
        try:
            await payment_services.verify_and_settle_payment(
                db, transaction_ref=transaction_ref
            )
        except Exception as exc:
            logger.exception("Squad webhook settle failed: %s", exc)

    elif event in ("transfer_complete", "transfer_failed"):
        payout = (
            db.query(payment_models.Payout)
            .filter(payment_models.Payout.payout_ref == transaction_ref)
            .first()
        )
        if payout:
            raw = (payload.get("Body") or {}).get(
                "transaction_status", ""
            )
            mapped = payment_utils.map_provider_status(raw)
            payout.status = {
                "SUCCESS": payment_models.PayoutStatusEnum.success,
                "PENDING": payment_models.PayoutStatusEnum.processing,
                "FAILED": payment_models.PayoutStatusEnum.failed,
            }[mapped]
            payout.raw_status = raw
            db.commit()

    elif event == "refund_successful":
        refund = (
            db.query(payment_models.Refund)
            .filter(
                payment_models.Refund.provider_refund_ref == transaction_ref
            )
            .first()
        )
        if refund:
            refund.status = payment_models.RefundStatusEnum.processed
            db.commit()

    return {"status": "ok"}


@router.post("/webhook/paystack")
async def paystack_webhook(
    request: Request, db: Session = Depends(get_db)
):
    raw_body = await request.body()
    signature = request.headers.get("x-paystack-signature", "")

    if not payment_utils.verify_paystack_webhook(raw_body, signature):
        logger.warning("Invalid Paystack webhook signature.")
        raise HTTPException(401, "Invalid signature.")

    try:
        payload = json.loads(raw_body)
    except Exception:
        raise HTTPException(400, "Invalid JSON.")

    event = payload.get("event")
    data = payload.get("data") or {}
    reference = data.get("reference")

    if event in ("charge.success", "charge.failed") and reference:
        try:
            await payment_services.verify_and_settle_payment(
                db, transaction_ref=reference
            )
        except Exception as exc:
            logger.exception("Paystack webhook settle failed: %s", exc)

    elif event in ("transfer.success", "transfer.failed", "transfer.reversed"):
        payout = (
            db.query(payment_models.Payout)
            .filter(payment_models.Payout.payout_ref == reference)
            .first()
        )
        if payout:
            status_map = {
                "transfer.success": payment_models.PayoutStatusEnum.success,
                "transfer.failed": payment_models.PayoutStatusEnum.failed,
                "transfer.reversed": payment_models.PayoutStatusEnum.reversed,
            }
            payout.status = status_map[event]
            payout.raw_status = event
            db.commit()

    elif event in ("refund.processed", "refund.failed"):
        refund = (
            db.query(payment_models.Refund)
            .filter(
                payment_models.Refund.provider_refund_ref
                == str(data.get("id") or "")
            )
            .first()
        )
        if refund:
            refund.status = (
                payment_models.RefundStatusEnum.processed
                if event == "refund.processed"
                else payment_models.RefundStatusEnum.failed
            )
            db.commit()

    return {"status": "ok"}


# ============================================================
# FIXED-PATH ENDPOINTS (must be declared before /{id})
# ============================================================

@router.get(
    "/my-payments",
    response_model=List[payment_schemas.PaymentOut],
)
def get_my_payments(
    status_filter: Optional[payment_models.PaymentStatusEnum] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    q = db.query(payment_models.Payment).filter(
        payment_models.Payment.user_id == current_user.id
    )
    if status_filter:
        q = q.filter(payment_models.Payment.status == status_filter)
    payments = q.order_by(payment_models.Payment.created_at.desc()).all()
    return [_payment_out(p) for p in payments]


@router.get(
    "/wallet/me",
    response_model=payment_schemas.WalletOut,
)
def get_my_wallet(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    wallet = payment_services.get_or_create_wallet(db, current_user.id)
    db.commit()
    db.refresh(wallet)
    return _wallet_out(wallet)


@router.get(
    "/transactions/me",
    response_model=List[payment_schemas.TransactionOut],
)
def get_my_transactions(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    transaction_type: Optional[
        payment_models.TransactionTypeEnum
    ] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    q = db.query(payment_models.Transaction).filter(
        payment_models.Transaction.user_id == current_user.id
    )
    if date_from:
        q = q.filter(
            payment_models.Transaction.transaction_date >= date_from
        )
    if date_to:
        q = q.filter(
            payment_models.Transaction.transaction_date <= date_to
        )
    if transaction_type:
        q = q.filter(
            payment_models.Transaction.transaction_type == transaction_type
        )
    txns = q.order_by(payment_models.Transaction.created_at.desc()).all()
    return [_transaction_out(t) for t in txns]


# ---------------- Statements ----------------

@router.post(
    "/statements/generate",
    response_model=payment_schemas.StatementOut,
)
def generate_statement(
    payload: payment_schemas.StatementGenerateIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    statement, txns = payment_services.generate_statement(
        db,
        user_id=current_user.id,
        period_start=payload.period_start,
        period_end=payload.period_end,
    )
    return _statement_out(statement, txns)


@router.get(
    "/statements/me",
    response_model=List[payment_schemas.StatementOut],
)
def list_my_statements(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    statements = (
        db.query(payment_models.Statement)
        .filter(payment_models.Statement.user_id == current_user.id)
        .order_by(payment_models.Statement.generated_at.desc())
        .all()
    )
    return [_statement_out(s, []) for s in statements]


# ---------------- Refunds ----------------

@router.post(
    "/refunds",
    response_model=payment_schemas.RefundOut,
    status_code=status.HTTP_201_CREATED,
)
def request_refund(
    payload: payment_schemas.RefundCreateIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    refund = payment_services.request_refund(
        db,
        user=current_user,
        payment_id=payload.payment_id,
        reason=payload.reason,
        is_partial=payload.is_partial,
        amount_kobo=payload.amount_kobo,
    )
    return _refund_out(refund)


@router.get(
    "/refunds/me",
    response_model=List[payment_schemas.RefundOut],
)
def list_my_refunds(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    refunds = (
        db.query(payment_models.Refund)
        .filter(payment_models.Refund.requested_by_id == current_user.id)
        .order_by(payment_models.Refund.created_at.desc())
        .all()
    )
    return [_refund_out(r) for r in refunds]


# ---------------- Payouts ----------------

@router.post(
    "/payouts",
    response_model=payment_schemas.PayoutOut,
    status_code=status.HTTP_201_CREATED,
)
def request_payout(
    payload: payment_schemas.PayoutCreateIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    if not current_user.can_offer_rides:
        raise HTTPException(
            403, "Only verified drivers can request payouts."
        )
    payout = payment_services.request_payout(
        db, driver=current_user, payload=payload
    )
    return _payout_out(payout)


@router.get(
    "/payouts/me",
    response_model=List[payment_schemas.PayoutOut],
)
def list_my_payouts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    payouts = (
        db.query(payment_models.Payout)
        .filter(payment_models.Payout.driver_id == current_user.id)
        .order_by(payment_models.Payout.created_at.desc())
        .all()
    )
    return [_payout_out(p) for p in payouts]


# ---------------- Admin ----------------

@router.get(
    "/admin/all-payments",
    response_model=List[payment_schemas.PaymentOut],
)
def admin_list_payments(
    status_filter: Optional[payment_models.PaymentStatusEnum] = None,
    provider: Optional[payment_models.PaymentProviderEnum] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required.")
    q = db.query(payment_models.Payment)
    if status_filter:
        q = q.filter(payment_models.Payment.status == status_filter)
    if provider:
        q = q.filter(payment_models.Payment.provider == provider)
    payments = q.order_by(payment_models.Payment.created_at.desc()).all()
    return [_payment_out(p) for p in payments]


@router.get(
    "/admin/all-refunds",
    response_model=List[payment_schemas.RefundOut],
)
def admin_list_refunds(
    status_filter: Optional[payment_models.RefundStatusEnum] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required.")
    q = db.query(payment_models.Refund)
    if status_filter:
        q = q.filter(payment_models.Refund.status == status_filter)
    refunds = q.order_by(payment_models.Refund.created_at.desc()).all()
    return [_refund_out(r) for r in refunds]


@router.post(
    "/admin/refunds/{refund_id}/review",
    response_model=payment_schemas.RefundOut,
)
async def admin_review_refund(
    refund_id: int,
    payload: payment_schemas.RefundAdminReviewIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required.")

    refund = (
        db.query(payment_models.Refund)
        .filter(payment_models.Refund.id == refund_id)
        .first()
    )
    if not refund:
        raise HTTPException(404, "Refund not found.")

    if not payload.approve:
        refund.status = payment_models.RefundStatusEnum.rejected
        refund.admin_note = payload.admin_note
        refund.reviewed_by_id = current_user.id
        refund.processed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(refund)
        return _refund_out(refund)

    refund = await payment_services.process_refund(
        db, refund=refund, admin_user=current_user
    )
    return _refund_out(refund)


@router.get(
    "/admin/all-payouts",
    response_model=List[payment_schemas.PayoutOut],
)
def admin_list_payouts(
    status_filter: Optional[payment_models.PayoutStatusEnum] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required.")
    q = db.query(payment_models.Payout)
    if status_filter:
        q = q.filter(payment_models.Payout.status == status_filter)
    payouts = q.order_by(payment_models.Payout.created_at.desc()).all()
    return [_payout_out(p) for p in payouts]


@router.post(
    "/admin/payouts/{payout_id}/review",
    response_model=payment_schemas.PayoutOut,
)
async def admin_review_payout(
    payout_id: int,
    payload: payment_schemas.PayoutAdminReviewIn,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required.")

    payout = (
        db.query(payment_models.Payout)
        .filter(payment_models.Payout.id == payout_id)
        .first()
    )
    if not payout:
        raise HTTPException(404, "Payout not found.")

    if not payload.approve:
        payout.status = payment_models.PayoutStatusEnum.failed
        payout.admin_note = payload.admin_note
        payout.processed_at = datetime.now(timezone.utc)

        # Return funds to driver
        wallet = payment_services.get_or_create_wallet(db, payout.driver_id)
        wallet.pending_balance_kobo -= payout.gross_amount_kobo
        wallet.available_balance_kobo += payout.gross_amount_kobo

        db.commit()
        db.refresh(payout)
        return _payout_out(payout)

    payout = await payment_services.process_payout(
        db, payout=payout, admin_user=current_user
    )
    return _payout_out(payout)


# ============================================================
# PAYMENT: GET ONE (LAST — path param swallows everything above)
# GET /payments/{payment_id}
# ============================================================

@router.get(
    "/{payment_id}",
    response_model=payment_schemas.PaymentOut,
)
def get_payment(
    payment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(oauth2.get_current_user),
):
    payment = (
        db.query(payment_models.Payment)
        .filter(payment_models.Payment.id == payment_id)
        .first()
    )
    if not payment:
        raise HTTPException(404, "Payment not found.")
    if payment.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(403, "Not allowed.")
    return _payment_out(payment)