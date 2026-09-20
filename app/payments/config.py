"""
app/payments/config.py

Central configuration for the payments module.
All env vars and economics live here so they can be imported,
mocked in tests, and adjusted per-environment.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# ENVIRONMENT
# ============================================================

ENVIRONMENT: str = os.getenv("ENVIRONMENT", "sandbox").lower()
IS_PRODUCTION: bool = ENVIRONMENT == "production"
IS_SANDBOX: bool = not IS_PRODUCTION


# ============================================================
# HELPERS
# ============================================================

def _normalize_base_url(url: Optional[str], strip_suffixes: tuple = ()) -> str:
    """Strip trailing slashes and known path suffixes to get a clean base."""
    if not url:
        return ""
    url = url.rstrip("/")
    for suffix in strip_suffixes:
        if url.endswith(suffix):
            url = url[: -len(suffix)]
    return url.rstrip("/")


def _first_set(*names: str) -> Optional[str]:
    """Return the first env var that is set and non-empty."""
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _mask(value: Optional[str]) -> str:
    if not value:
        return "<unset>"
    if len(value) <= 16:
        return "<set>"
    return f"{value[:12]}…{value[-4:]}"


# ============================================================
# SQUAD
# ============================================================

SQUAD_API_KEY: Optional[str] = _first_set(
    "SQUAD_SANDBOX_API_KEY" if IS_SANDBOX else "SQUAD_API_KEY",
    "SQUAD_API_KEY",
    "SQUAD_SANDBOX_API_KEY",
)

_raw_squad_url: str = (
    (_first_set("SQUAD_SANDBOX_URL") if IS_SANDBOX else _first_set("SQUAD_API_URL"))
    or "https://sandbox-api-d.squadco.com"
)

SQUAD_BASE_URL: str = _normalize_base_url(
    _raw_squad_url,
    strip_suffixes=("/transaction/verify",),
)

SQUAD_VERIFY_URL: str = f"{SQUAD_BASE_URL}/transaction/verify/"

SQUAD_CALLBACK_URL: Optional[str] = os.getenv(
    "SQUAD_CALLBACK_URL", "https://yourapp.com/payment/callback"
)


# ============================================================
# PAYSTACK
# ============================================================

PAYSTACK_SECRET_KEY: Optional[str] = _first_set(
    "PAYSTACK_SANDBOX_SECRET_KEY" if IS_SANDBOX else "PAYSTACK_SECRET_KEY",
    "PAYSTACK_SECRET_KEY",
    "PAYSTACK_SANDBOX_SECRET_KEY",
    "PAYSTACK_API_KEY",
)

_raw_paystack_url: str = (
    _first_set("PAYSTACK_API_URL") or "https://api.paystack.co"
)

PAYSTACK_BASE_URL: str = _normalize_base_url(
    _raw_paystack_url,
    strip_suffixes=("/transaction/verify",),
)

PAYSTACK_VERIFY_URL: str = f"{PAYSTACK_BASE_URL}/transaction/verify/"

PAYSTACK_CALLBACK_URL: Optional[str] = os.getenv(
    "PAYSTACK_CALLBACK_URL", "https://yourapp.com/payment/callback"
)


# ============================================================
# PLATFORM ECONOMICS
# ============================================================

PLATFORM_COMMISSION_RATE: float = float(
    os.getenv("PLATFORM_COMMISSION_RATE", "0.10")
)

PAYOUT_TAX_RATE: float = float(
    os.getenv("PAYOUT_TAX_RATE", "0.05")
)

MAX_PAYOUT_KOBO: int = int(
    os.getenv("MAX_PAYOUT_KOBO", "100000000")
)

DEFAULT_CURRENCY: str = os.getenv("DEFAULT_CURRENCY", "NGN")


# ============================================================
# TIMEOUTS & RETRY
# ============================================================

PROVIDER_HTTP_TIMEOUT: int = int(
    os.getenv("PROVIDER_HTTP_TIMEOUT", "30")
)

WEBHOOK_MAX_RETRIES: int = int(os.getenv("WEBHOOK_MAX_RETRIES", "3"))
WEBHOOK_RETRY_BACKOFF_SECONDS: float = float(
    os.getenv("WEBHOOK_RETRY_BACKOFF_SECONDS", "1.5")
)


# ============================================================
# STATUS MAPPING
# ============================================================

STATUS_MAPPING: dict = {
    "success": "SUCCESS",
    "completed": "SUCCESS",
    "paid": "SUCCESS",
    "successful": "SUCCESS",

    "pending": "PENDING",
    "ongoing": "PENDING",
    "processing": "PENDING",
    "queued": "PENDING",
    "initiated": "PENDING",
    "sent": "PENDING",

    "failed": "FAILED",
    "abandoned": "FAILED",
    "reversed": "FAILED",
    "expired": "FAILED",
    "cancelled": "FAILED",
    "canceled": "FAILED",
    "declined": "FAILED",
}


def map_provider_status(raw_status: Optional[str]) -> str:
    """Map a provider status string to SUCCESS | PENDING | FAILED."""
    if not raw_status:
        return "FAILED"
    return STATUS_MAPPING.get(raw_status.strip().lower(), "FAILED")


# ============================================================
# STARTUP LOGGING
# ============================================================

def _log_config() -> None:
    logger.info("Payments config loaded: env=%s", ENVIRONMENT)
    logger.info(
        "  Squad    base=%s key=%s",
        SQUAD_BASE_URL, _mask(SQUAD_API_KEY),
    )
    logger.info(
        "  Paystack base=%s key=%s",
        PAYSTACK_BASE_URL, _mask(PAYSTACK_SECRET_KEY),
    )
    logger.info(
        "  Economics commission=%.2f tax=%.2f max_payout=%.2f %s",
        PLATFORM_COMMISSION_RATE,
        PAYOUT_TAX_RATE,
        MAX_PAYOUT_KOBO / 100,
        DEFAULT_CURRENCY,
    )

    if not SQUAD_API_KEY:
        logger.warning("SQUAD_API_KEY is not set — Squad calls will fail.")
    if not PAYSTACK_SECRET_KEY:
        logger.warning(
            "PAYSTACK_SECRET_KEY is not set — Paystack calls will fail."
        )


_log_config()