"""
app/payments/utils.py

Provider HTTP helpers, reference generation, amount conversion,
webhook signature verification.
"""

import hmac
import hashlib
import asyncio
import time
import uuid
import logging
from typing import Optional, Dict, Any

import requests

from app.payments import config as cfg

logger = logging.getLogger(__name__)


# ============================================================
# AMOUNT CONVERSION
# ============================================================

def naira_to_kobo(amount_naira) -> int:
    """N50,000 -> 5000000"""
    return int(round(float(amount_naira) * 100))


def kobo_to_naira(amount_kobo: int) -> float:
    """5000000 -> 50000.0"""
    return int(amount_kobo) / 100.0


# ============================================================
# TRANSACTION REFERENCE GENERATION
# ============================================================

def _ts() -> str:
    """
    Millisecond timestamp + short uuid suffix.
    Avoids collisions when many refs are generated in the same ms.
    """
    return f"{int(time.time() * 1000)}{uuid.uuid4().hex[:6]}"


def generate_payment_ref(user_id: int) -> str:
    return f"BOOKING-{user_id}-{_ts()}"


def generate_payout_ref(driver_id: int) -> str:
    return f"PAYOUT-{driver_id}-{_ts()}"


def generate_refund_ref(booking_id: int) -> str:
    return f"REFUND-{booking_id}-{_ts()}"


# ============================================================
# PAYOUT MATH
# ============================================================

def compute_payout_breakdown(gross_amount_kobo: int) -> Dict[str, int]:
    commission_kobo = int(
        round(gross_amount_kobo * cfg.PLATFORM_COMMISSION_RATE)
    )
    after_commission = gross_amount_kobo - commission_kobo
    tax_kobo = int(round(after_commission * cfg.PAYOUT_TAX_RATE))
    net_amount_kobo = after_commission - tax_kobo

    return {
        "commission_kobo": commission_kobo,
        "tax_kobo": tax_kobo,
        "net_amount_kobo": net_amount_kobo,
    }


# ============================================================
# HTTP HELPERS
# ============================================================

def _safe_json(resp) -> Dict[str, Any]:
    try:
        return resp.json()
    except Exception:
        return {"raw_text": resp.text}


def _do_post(url: str, payload: dict, headers: dict) -> Dict[str, Any]:
    r = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=cfg.PROVIDER_HTTP_TIMEOUT,
    )
    if r.status_code >= 400:
        logger.error("POST %s -> %s: %s", url, r.status_code, r.text)
    r.raise_for_status()
    return _safe_json(r)


def _do_get(url: str, headers: dict) -> Dict[str, Any]:
    r = requests.get(
        url,
        headers=headers,
        timeout=cfg.PROVIDER_HTTP_TIMEOUT,
    )
    if r.status_code >= 400:
        logger.error("GET %s -> %s: %s", url, r.status_code, r.text)
    r.raise_for_status()
    return _safe_json(r)


# ============================================================
# SQUAD
# ============================================================

def _squad_headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg.SQUAD_API_KEY}",
    }


async def squad_initialize_payment(
    email: str,
    amount_kobo: int,
    transaction_ref: str,
    callback_url: Optional[str] = None,
    currency: Optional[str] = None,
) -> Dict[str, Any]:
    url = f"{cfg.SQUAD_BASE_URL}/transaction/initiate"
    payload = {
        "email": email,
        "amount": amount_kobo,
        "currency": currency or cfg.DEFAULT_CURRENCY,
        "initiate_type": "inline",
        "transaction_ref": transaction_ref,
        "payment_channels": ["card", "bank", "ussd", "bank_transfer"],
    }
    callback_url = callback_url or cfg.SQUAD_CALLBACK_URL
    if callback_url:
        payload["callback_url"] = callback_url

    return await asyncio.to_thread(
        _do_post, url, payload, _squad_headers()
    )


async def squad_verify_payment(transaction_ref: str) -> Dict[str, Any]:
    url = f"{cfg.SQUAD_VERIFY_URL}{transaction_ref}"
    return await asyncio.to_thread(_do_get, url, _squad_headers())


async def squad_refund_payment(
    transaction_ref: str,
    reason: str,
    partial_amount_kobo: Optional[int] = None,
) -> Dict[str, Any]:
    url = f"{cfg.SQUAD_BASE_URL}/transaction/refund"
    payload = {
        "gateway_transaction_ref": transaction_ref,
        "transaction_ref": transaction_ref,
        "refund_type": "Partial" if partial_amount_kobo else "Full",
        "reason_for_refund": reason,
    }
    if partial_amount_kobo:
        payload["amount"] = partial_amount_kobo

    return await asyncio.to_thread(
        _do_post, url, payload, _squad_headers()
    )


async def squad_transfer(
    transaction_ref: str,
    amount_kobo: int,
    bank_code: str,
    account_number: str,
    account_name: str,
    remark: str = "Ride earnings payout",
    currency_id: Optional[str] = None,
) -> Dict[str, Any]:
    url = f"{cfg.SQUAD_BASE_URL}/payout/transfer"
    payload = {
        "transaction_ref": transaction_ref,
        "amount": amount_kobo,
        "bank_code": bank_code,
        "account_number": account_number,
        "account_name": account_name,
        "currency_id": currency_id or cfg.DEFAULT_CURRENCY,
        "remark": remark,
    }
    return await asyncio.to_thread(
        _do_post, url, payload, _squad_headers()
    )


async def squad_account_lookup(
    bank_code: str, account_number: str
) -> Dict[str, Any]:
    url = f"{cfg.SQUAD_BASE_URL}/payout/account/lookup"
    payload = {"bank_code": bank_code, "account_number": account_number}
    return await asyncio.to_thread(
        _do_post, url, payload, _squad_headers()
    )


async def squad_list_banks() -> Dict[str, Any]:
    url = f"{cfg.SQUAD_BASE_URL}/payout/banks"
    return await asyncio.to_thread(_do_get, url, _squad_headers())


# ============================================================
# PAYSTACK
# ============================================================

def _paystack_headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg.PAYSTACK_SECRET_KEY}",
    }


async def paystack_initialize_payment(
    email: str,
    amount_kobo: int,
    reference: str,
    callback_url: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    url = f"{cfg.PAYSTACK_BASE_URL}/transaction/initialize"
    payload = {
        "email": email,
        "amount": amount_kobo,
        "currency": cfg.DEFAULT_CURRENCY,
        "reference": reference,
        "channels": ["card", "bank", "ussd", "bank_transfer"],
    }
    callback_url = callback_url or cfg.PAYSTACK_CALLBACK_URL
    if callback_url:
        payload["callback_url"] = callback_url
    if metadata:
        payload["metadata"] = metadata

    return await asyncio.to_thread(
        _do_post, url, payload, _paystack_headers()
    )


async def paystack_verify_payment(reference: str) -> Dict[str, Any]:
    url = f"{cfg.PAYSTACK_VERIFY_URL}{reference}"
    return await asyncio.to_thread(_do_get, url, _paystack_headers())


async def paystack_refund_payment(
    transaction_ref: str,
    amount_kobo: Optional[int] = None,
    note: str = "Booking cancelled",
) -> Dict[str, Any]:
    url = f"{cfg.PAYSTACK_BASE_URL}/refund"
    payload = {
        "transaction": transaction_ref,
        "customer_note": note,
        "merchant_note": note,
    }
    if amount_kobo:
        payload["amount"] = amount_kobo

    return await asyncio.to_thread(
        _do_post, url, payload, _paystack_headers()
    )


async def paystack_create_transfer_recipient(
    name: str,
    account_number: str,
    bank_code: str,
) -> Dict[str, Any]:
    url = f"{cfg.PAYSTACK_BASE_URL}/transferrecipient"
    payload = {
        "type": "nuban",
        "name": name,
        "account_number": account_number,
        "bank_code": bank_code,
        "currency": cfg.DEFAULT_CURRENCY,
    }
    return await asyncio.to_thread(
        _do_post, url, payload, _paystack_headers()
    )


async def paystack_initiate_transfer(
    amount_kobo: int,
    recipient_code: str,
    reason: str,
    reference: str,
) -> Dict[str, Any]:
    url = f"{cfg.PAYSTACK_BASE_URL}/transfer"
    payload = {
        "source": "balance",
        "amount": amount_kobo,
        "recipient": recipient_code,
        "reason": reason,
        "reference": reference,
    }
    return await asyncio.to_thread(
        _do_post, url, payload, _paystack_headers()
    )


# ============================================================
# WEBHOOK VERIFICATION
# ============================================================      
def verify_squad_webhook(payload: bytes, signature: str) -> bool:
    if not cfg.SQUAD_API_KEY or not signature:
        return False
    expected = hmac.new(
        cfg.SQUAD_API_KEY.encode(),
        payload,
        hashlib.sha512,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

