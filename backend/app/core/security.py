"""API key authentication."""

import secrets

from fastapi import Header, HTTPException, status

from app.core.config import settings
from app.core.logging import logger


async def verify_api_key(x_api_key: str | None = Header(default=None)) -> str:
    """Verify the X-API-Key header against the configured key list.

    Behavior:
    - If AUTH_DISABLED=true, always allow (dev convenience). Logs a warning once.
    - If API_KEYS is empty, treat as misconfiguration in production; allow in dev.
    - Compares using constant-time comparison.
    """
    if settings.AUTH_DISABLED:
        return "auth-disabled"

    if not settings.API_KEYS:
        if settings.is_production:
            logger.error("API_KEYS not configured in production — refusing request")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Server misconfigured: API_KEYS not set",
            )
        # dev: allow but warn
        logger.warning("API_KEYS empty (dev mode) — allowing request without auth")
        return "dev-no-auth"

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    for key in settings.API_KEYS:
        if secrets.compare_digest(x_api_key, key):
            # Return a short fingerprint for logging, never the key itself
            return f"key-{x_api_key[:6]}…"

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
    )
