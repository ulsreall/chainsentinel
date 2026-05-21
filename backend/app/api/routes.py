"""API Routes — Contract analysis, batch processing, and stats."""

from __future__ import annotations

import asyncio
import time

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import logger
from app.core.security import verify_api_key
from app.core.token_tracker import BudgetExceededError, TokenTracker
from app.services.analysis_pipeline import AnalysisPipeline
from app.services.mimo_client import MiMoClient
from app.utils.contract_validator import extract_contract_name, validate_solidity

router = APIRouter()


class AnalyzeRequest(BaseModel):
    code: str = Field(..., min_length=1)
    contract_name: str | None = None
    network: str | None = "ethereum"


class BatchAnalyzeRequest(BaseModel):
    contracts: list[AnalyzeRequest] = Field(..., min_length=1, max_length=10)
    parallel: bool = True
    max_concurrent: int = Field(default=3, ge=1, le=5)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10_000)
    context: str | None = None


def _get_pipeline(request: Request) -> AnalysisPipeline:
    mimo: MiMoClient = request.app.state.mimo_client
    tracker: TokenTracker = request.app.state.token_tracker
    return AnalysisPipeline(mimo, tracker)


def _check_size(code: str) -> None:
    """Reject contracts that exceed configured limits."""
    size_kb = len(code.encode("utf-8")) / 1024
    if size_kb > settings.MAX_CONTRACT_SIZE_KB:
        raise HTTPException(
            413,
            f"Contract too large: {size_kb:.1f} KB > {settings.MAX_CONTRACT_SIZE_KB} KB",
        )
    loc = code.count("\n") + 1
    if loc > settings.MAX_CONTRACT_LOC:
        raise HTTPException(
            413,
            f"Contract too long: {loc} lines > {settings.MAX_CONTRACT_LOC}",
        )


def _validate_contract(code: str) -> None:
    if not code.strip():
        raise HTTPException(400, "Contract code is empty")
    _check_size(code)
    validation = validate_solidity(code)
    if not validation["valid"]:
        raise HTTPException(400, f"Invalid Solidity code: {validation['error']}")


def _check_budget_or_raise(tracker: TokenTracker) -> None:
    try:
        tracker.check_budget()
    except BudgetExceededError as e:
        raise HTTPException(429, str(e)) from e


@router.post("/analyze", dependencies=[Depends(verify_api_key)])
async def analyze_contract(req: AnalyzeRequest, request: Request):
    """Analyze a single smart contract with multi-agent pipeline."""
    _validate_contract(req.code)
    tracker: TokenTracker = request.app.state.token_tracker
    _check_budget_or_raise(tracker)

    contract_name = req.contract_name or extract_contract_name(req.code)
    pipeline = _get_pipeline(request)
    return await pipeline.analyze(req.code, contract_name)


@router.post("/batch-analyze", dependencies=[Depends(verify_api_key)])
async def batch_analyze(req: BatchAnalyzeRequest, request: Request):
    """Analyze multiple contracts in batch for high-throughput auditing."""
    for c in req.contracts:
        _validate_contract(c.code)

    tracker: TokenTracker = request.app.state.token_tracker
    _check_budget_or_raise(tracker)

    pipeline = _get_pipeline(request)

    if req.parallel:
        semaphore = asyncio.Semaphore(req.max_concurrent)

        async def limited_analyze(contract: AnalyzeRequest):
            async with semaphore:
                name = contract.contract_name or extract_contract_name(contract.code)
                return await pipeline.analyze(contract.code, name)

        tasks = [limited_analyze(c) for c in req.contracts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            "batch_id": str(int(time.time())),
            "total_contracts": len(req.contracts),
            "parallel": True,
            "results": [
                r if not isinstance(r, Exception) else {"error": str(r)} for r in results
            ],
        }

    results = []
    for contract in req.contracts:
        name = contract.contract_name or extract_contract_name(contract.code)
        results.append(await pipeline.analyze(contract.code, name))

    return {
        "batch_id": str(int(time.time())),
        "total_contracts": len(req.contracts),
        "parallel": False,
        "results": results,
    }


@router.post("/upload", dependencies=[Depends(verify_api_key)])
async def upload_contract(
    request: Request,
    file: UploadFile = File(...),
    contract_name: str | None = Form(None),
):
    """Upload a .sol file for analysis."""
    if not file.filename or not file.filename.endswith(".sol"):
        raise HTTPException(400, "Only .sol files are supported")

    # Stream-read with hard cap
    max_bytes = settings.MAX_CONTRACT_SIZE_KB * 1024
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(413, f"File exceeds {settings.MAX_CONTRACT_SIZE_KB} KB limit")
        chunks.append(chunk)

    try:
        code = b"".join(chunks).decode("utf-8")
    except UnicodeDecodeError as e:
        raise HTTPException(400, "File is not valid UTF-8 text") from e

    _validate_contract(code)
    tracker: TokenTracker = request.app.state.token_tracker
    _check_budget_or_raise(tracker)

    name = contract_name or file.filename.replace(".sol", "")
    pipeline = _get_pipeline(request)
    return await pipeline.analyze(code, name)


@router.post("/chat", dependencies=[Depends(verify_api_key)])
async def chat_with_agent(req: ChatRequest, request: Request):
    """Chat with the security analysis agent for Q&A."""
    mimo: MiMoClient = request.app.state.mimo_client
    tracker: TokenTracker = request.app.state.token_tracker
    _check_budget_or_raise(tracker)

    system = (
        "You are ChainSentinel AI, a smart contract security expert. "
        "Answer questions about Solidity security, DeFi vulnerabilities, "
        "audit best practices, and gas optimization. Be concise and technical."
    )

    result = await mimo.chat(
        messages=[{"role": "user", "content": req.message}],
        system=system,
        temperature=0.4,
    )
    tokens = result.get("tokens", {}).get("total", 0)
    tracker.record_usage(tokens, agent="chat_agent")

    return {
        "response": result.get("content", ""),
        "tokens_used": tokens,
        "model": result.get("model"),
    }


@router.post("/chat/stream", dependencies=[Depends(verify_api_key)])
async def chat_stream(req: ChatRequest, request: Request):
    """Streaming variant of /chat — returns server-sent events as plain text chunks."""
    mimo: MiMoClient = request.app.state.mimo_client
    tracker: TokenTracker = request.app.state.token_tracker
    _check_budget_or_raise(tracker)

    system = (
        "You are ChainSentinel AI, a smart contract security expert. "
        "Be concise and technical."
    )

    async def event_gen():
        try:
            async for token in mimo.stream_chat(
                messages=[{"role": "user", "content": req.message}],
                system=system,
            ):
                yield token
        except Exception as e:  # noqa: BLE001
            logger.exception("Streaming failed")
            yield f"\n[error] {e}"
        finally:
            # Streaming endpoint doesn't get usage info from upstream; record a small placeholder
            tracker.record_usage(0, agent="chat_stream")

    return StreamingResponse(event_gen(), media_type="text/plain")


@router.get("/stats", dependencies=[Depends(verify_api_key)])
async def get_stats(request: Request):
    """Get token usage statistics."""
    tracker: TokenTracker = request.app.state.token_tracker
    return tracker.get_stats()


@router.get("/stats/history", dependencies=[Depends(verify_api_key)])
async def get_stats_history(request: Request, limit: int = 50):
    """Get token usage history."""
    tracker: TokenTracker = request.app.state.token_tracker
    return {"history": tracker.get_history(min(max(limit, 1), 1000))}


@router.get("/stats/trend", dependencies=[Depends(verify_api_key)])
async def get_stats_trend(request: Request, days: int = 7):
    """Get daily token usage trend."""
    tracker: TokenTracker = request.app.state.token_tracker
    return {"trend": tracker.get_daily_trend(min(max(days, 1), 90))}
