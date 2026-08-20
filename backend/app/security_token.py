import logging
import os
from http import HTTPStatus

from fastapi import HTTPException

from app.app_config import get_application_config

logger = logging.getLogger(__name__)


def normalize_security_token(value: str | None) -> str | None:
    """
    Normalize a SEC_TOKEN-equivalent value for comparison.

    Casefolds the value and strips a single trailing '!' so that links whose
    trailing exclamation mark was dropped by chat-app auto-link parsers
    (WhatsApp, Telegram, etc.) still validate. Returns None for None or empty
    input so callers can keep their existing "Security token required" branch.
    """
    if value is None:
        return None
    normalized = value.casefold()
    if normalized.endswith("!"):
        normalized = normalized[:-1]
    return normalized or None


def is_registration_code_disabled() -> bool:
    """
    Whether GLOBAL_DISABLE_REGISTRATION_CODE is enabled.

    Reads the application configuration when it is set up, and falls back to the
    environment variable when it is not (eg. in isolated unit tests).
    """
    try:
        return get_application_config().disable_registration_code
    except RuntimeError:
        return os.getenv("GLOBAL_DISABLE_REGISTRATION_CODE", "").lower() == "true"


def validate_report_token(report_token: str | None) -> None:
    """
    Validate a secure-link report token against SEC_TOKEN.

    Raises 401 when the token (or SEC_TOKEN) is missing and 403 when it does not
    match. Validation is skipped entirely when GLOBAL_DISABLE_REGISTRATION_CODE
    is enabled, because in that deployment mode registration codes carry no
    access control and the frontend does not send a report token.

    This bypass is deliberately scoped to creating/updating user preferences.
    Other secure-link consumers (eg. the invitation status endpoint) keep
    validating the token unconditionally.
    """
    if is_registration_code_disabled():
        logger.debug("GLOBAL_DISABLE_REGISTRATION_CODE is enabled - skipping security token validation.")
        return

    normalized_report_token = normalize_security_token(report_token)
    normalized_sec_token = normalize_security_token(os.getenv("SEC_TOKEN"))
    if not normalized_report_token or not normalized_sec_token:
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Security token required")
    if normalized_report_token != normalized_sec_token:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Invalid security token")
