"""Structured logging setup."""

import logging
import sys

from app.core.config import settings


def setup_logging() -> logging.Logger:
    """Configure root logger with structured format."""
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logger = logging.getLogger()
    if logger.handlers:
        # Already configured
        return logging.getLogger("chainsentinel")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.setLevel(level)

    # Tone down noisy libs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    return logging.getLogger("chainsentinel")


logger = setup_logging()
