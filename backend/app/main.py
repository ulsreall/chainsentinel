"""ChainSentinel — AI-Powered Smart Contract Security Platform.

FastAPI Backend with MiMo Multi-Agent Analysis Pipeline.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.routes import router
from app.core.config import settings
from app.core.logging import logger
from app.core.token_tracker import TokenTracker
from app.services.mimo_client import MiMoClient

load_dotenv()


def _resolve_default_limit() -> str:
    # Most permissive of the four → falls back to analyze rate
    return settings.RATE_LIMIT_ANALYZE


limiter = Limiter(key_func=get_remote_address, default_limits=[_resolve_default_limit()])


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ChainSentinel starting | env=%s model=%s", settings.APP_ENV, settings.MIMO_MODEL)
    if settings.is_production:
        if not settings.MIMO_API_KEY:
            logger.error("MIMO_API_KEY missing in production")
        if not settings.API_KEYS and not settings.AUTH_DISABLED:
            logger.error("API_KEYS missing in production — endpoints will return 503")
        if "*" in settings.ALLOWED_ORIGINS:
            logger.warning("ALLOWED_ORIGINS='*' in production — tighten this")

    app.state.token_tracker = TokenTracker()
    app.state.mimo_client = MiMoClient(
        settings.MIMO_API_KEY, settings.MIMO_BASE_URL, settings.MIMO_MODEL
    )
    yield
    logger.info("ChainSentinel shutting down")


app = FastAPI(
    title="ChainSentinel",
    description="AI-Powered Smart Contract Security Platform",
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS — configurable via env, no wildcard with credentials
allow_credentials = "*" not in settings.ALLOWED_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=allow_credentials,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": "ChainSentinel",
        "version": "1.0.0",
        "status": "running",
        "model": settings.MIMO_MODEL,
        "endpoints": {
            "docs": "/docs",
            "health": "/api/health",
            "analyze": "/api/analyze",
            "batch": "/api/batch-analyze",
            "stats": "/api/stats",
        },
    }


@app.get("/api/health")
async def health(request: Request):
    tracker: TokenTracker = request.app.state.token_tracker
    stats = tracker.get_stats()
    return {
        "status": "healthy",
        "uptime": stats["uptime_seconds"],
        "tokens_used_today": stats["total_tokens_today"],
        "analyses_completed": stats["analyses_completed"],
        "model": settings.MIMO_MODEL,
    }
