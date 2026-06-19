"""Admin-surface authentication.

A single secret (``ADMIN_TOKEN``) gates the staff admin panel and report downloads.
It is deliberately separate from ``SEC_TOKEN`` (which authorizes student registration
links) so that a leaked registration link cannot reach admin tooling.
"""
import logging
import os
from http import HTTPStatus

from fastapi import HTTPException, Query, Request

from app.security_token import normalize_security_token
from common_libs.time_utilities import get_now

logger = logging.getLogger(__name__)

ADMIN_TOKEN_ENV = "ADMIN_TOKEN"  # nosec B105 - environment variable name, not a secret value


async def require_admin_token(
    request: Request,
    token: str | None = Query(default=None, description="Admin access token"),
) -> None:
    """Gate an admin endpoint on the ``ADMIN_TOKEN`` secret.

    Raises 503 if the secret is not configured for the environment, 401 if the
    caller supplied no token, 403 if it does not match. Audit-logs every
    authorized access (the token itself is never logged). Reuses
    :func:`normalize_security_token` so chat-app link mangling is tolerated the
    same way as for ``SEC_TOKEN``.
    """
    normalized_admin_token = normalize_security_token(os.getenv(ADMIN_TOKEN_ENV))
    if not normalized_admin_token:
        raise HTTPException(status_code=HTTPStatus.SERVICE_UNAVAILABLE, detail="Admin access is not configured")

    normalized_token = normalize_security_token(token)
    if not normalized_token:
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Admin token required")
    if normalized_token != normalized_admin_token:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Invalid admin token")

    logger.info(
        "Admin endpoint accessed",
        extra={
            "action": "admin_access",
            "path": request.url.path,
            "ip_address": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "timestamp": get_now().isoformat(),
        },
    )
