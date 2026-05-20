"""API Routes — Contract analysis, batch processing, and stats."""

import asyncio
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from pydantic import BaseModel

from app.services.analysis_pipeline import AnalysisPipeline
from app.services.mimo_client import MiMoClient
from app.core.token_tracker import TokenTracker
from app.utils.contract_validator import validate_solidity, extract_contract_name

router = APIRouter()


class AnalyzeRequest(BaseModel):
    code: str
    contract_name: Optional[str] = None
    network: Optional[str] = "ethereum"


class BatchAnalyzeRequest(BaseModel):
    contracts: list[AnalyzeRequest]
    parallel: bool = True
    max_concurrent: int = 3


class ChatRequest(BaseModel):
    message: str
    context: Optional[str] = None


def _get_pipeline(request: Request) -> AnalysisPipeline:
    mimo: MiMoClient = request.app.state.mimo_client
    tracker: TokenTracker = request.app.state.token_tracker
    return AnalysisPipeline(mimo, tracker)


@router.post("/analyze")
async def analyze_contract(req: AnalyzeRequest, request: Request):
    """Analyze a single smart contract with multi-agent pipeline."""
    if not req.code.strip():
        raise HTTPException(400, "Contract code is empty")

    validation = validate_solidity(req.code)
    if not validation["valid"]:
        raise HTTPException(400, f"Invalid Solidity code: {validation['error']}")

    contract_name = req.contract_name or extract_contract_name(req.code)
    pipeline = _get_pipeline(request)

    result = await pipeline.analyze(req.code, contract_name)
    return result


@router.post("/batch-analyze")
async def batch_analyze(req: BatchAnalyzeRequest, request: Request):
    """Analyze multiple contracts in batch for high-throughput auditing."""
    if len(req.contracts) > 10:
        raise HTTPException(400, "Maximum 10 contracts per batch")

    pipeline = _get_pipeline(request)

    if req.parallel:
        semaphore = asyncio.Semaphore(req.max_concurrent)

        async def limited_analyze(contract):
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
                r if not isinstance(r, Exception) else {"error": str(r)}
                for r in results
            ],
        }
    else:
        results = []
        for contract in req.contracts:
            name = contract.contract_name or extract_contract_name(contract.code)
            result = await pipeline.analyze(contract.code, name)
            results.append(result)

        return {
            "batch_id": str(int(time.time())),
            "total_contracts": len(req.contracts),
            "parallel": False,
            "results": results,
        }


@router.post("/upload")
async def upload_contract(
    file: UploadFile = File(...),
    contract_name: Optional[str] = Form(None),
    request: Request = None,
):
    """Upload a .sol file for analysis."""
    if not file.filename.endswith(".sol"):
        raise HTTPException(400, "Only .sol files are supported")

    content = await file.read()
    code = content.decode("utf-8")

    name = contract_name or file.filename.replace(".sol", "")
    pipeline = _get_pipeline(request)
    result = await pipeline.analyze(code, name)
    return result


@router.post("/chat")
async def chat_with_agent(req: ChatRequest, request: Request):
    """Chat with the security analysis agent for Q&A."""
    mimo: MiMoClient = request.app.state.mimo_client
    tracker: TokenTracker = request.app.state.token_tracker

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


@router.get("/stats")
async def get_stats(request: Request):
    """Get token usage statistics."""
    tracker: TokenTracker = request.app.state.token_tracker
    return tracker.get_stats()


@router.get("/stats/history")
async def get_stats_history(request: Request, limit: int = 50):
    """Get token usage history."""
    tracker: TokenTracker = request.app.state.token_tracker
    return {"history": tracker.get_history(limit)}


@router.get("/stats/trend")
async def get_stats_trend(request: Request, days: int = 7):
    """Get daily token usage trend."""
    tracker: TokenTracker = request.app.state.token_tracker
    return {"trend": tracker.get_daily_trend(days)}
