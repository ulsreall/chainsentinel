"""
ChainSentinel — AI-Powered Smart Contract Security Platform
FastAPI Backend with MiMo Multi-Agent Analysis Pipeline
"""

import os
import time
import uuid
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from app.core.config import settings
from app.core.token_tracker import TokenTracker
from app.api.routes import router
from app.services.mimo_client import MiMoClient

load_dotenv()

token_tracker = TokenTracker()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    print("🛡️ ChainSentinel starting...")
    print(f"   Model: {settings.MIMO_MODEL}")
    print(f"   Token budget: {settings.DAILY_TOKEN_BUDGET:,}/day")
    yield
    print("🛡️ ChainSentinel shutting down...")

app = FastAPI(
    title="ChainSentinel",
    description="AI-Powered Smart Contract Security Platform — Multi-agent analysis pipeline using Xiaomi MiMo",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inject token tracker into app state
app.state.token_tracker = token_tracker
app.state.mimo_client = MiMoClient(settings.MIMO_API_KEY, settings.MIMO_BASE_URL, settings.MIMO_MODEL)

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
        }
    }

@app.get("/api/health")
async def health():
    stats = token_tracker.get_stats()
    return {
        "status": "healthy",
        "uptime": stats["uptime_seconds"],
        "tokens_used_today": stats["total_tokens_today"],
        "analyses_completed": stats["analyses_completed"],
        "model": settings.MIMO_MODEL,
    }
