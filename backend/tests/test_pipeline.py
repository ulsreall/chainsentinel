"""Tests for AnalysisPipeline."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.core.token_tracker import TokenTracker
from app.services.analysis_pipeline import AnalysisPipeline


class FakeMiMo:
    """Mock MiMo client that returns deterministic, agent-tagged responses."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.concurrent_peak = 0
        self._inflight = 0
        self._lock = asyncio.Lock()

    async def analyze_code(
        self, code: str, agent_role: str, context: str = "", temperature: float = 0.2
    ) -> dict[str, Any]:
        async with self._lock:
            self._inflight += 1
            self.concurrent_peak = max(self.concurrent_peak, self._inflight)
        try:
            await asyncio.sleep(0.02)  # let other coroutines schedule
        finally:
            async with self._lock:
                self._inflight -= 1

        self.calls.append({"agent": agent_role, "context": context, "code_len": len(code)})
        return {
            "content": f"[{agent_role}] result for {context or 'full'}",
            "tokens": {"prompt": 100, "completion": 50, "total": 150},
            "elapsed_seconds": 0.02,
            "model": "fake",
            "error": None,
        }


SAMPLE_CONTRACT = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract Sample {
    uint256 public x;
    function setX(uint256 _x) external { x = _x; }
}
"""


@pytest.mark.asyncio
async def test_analyze_runs_four_agents(tmp_path):
    tracker = TokenTracker(log_file=str(tmp_path / "log.jsonl"), daily_budget=0)
    fake = FakeMiMo()
    pipeline = AnalysisPipeline(fake, tracker)

    result = await pipeline.analyze(SAMPLE_CONTRACT, "Sample")

    assert result["agents_used"] == 4
    assert result["total_tokens_used"] == 150 * 4
    # Phase 1 has 3 agents — they should run concurrently
    assert fake.concurrent_peak >= 2, "phase 1 agents should run in parallel"


@pytest.mark.asyncio
async def test_chunked_analysis_runs_chunks_in_parallel(tmp_path):
    long_code = "// SPDX-License-Identifier: MIT\npragma solidity ^0.8.19;\ncontract Big {\n"
    long_code += "\n".join(f"    uint256 v{i};" for i in range(800))
    long_code += "\n}\n"

    tracker = TokenTracker(log_file=str(tmp_path / "log.jsonl"), daily_budget=0)
    fake = FakeMiMo()
    pipeline = AnalysisPipeline(fake, tracker)

    result = await pipeline.analyze(long_code, "Big")
    assert result["chunks_processed"] > 1
    # 3 phase-1 agents × N chunks should produce significant concurrency
    assert fake.concurrent_peak >= 3


def test_chunk_code_validates_overlap():
    pipeline = AnalysisPipeline(mimo_client=None, token_tracker=None)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        pipeline._chunk_code("a\nb\nc", chunk_size=2, overlap=2)
    with pytest.raises(ValueError):
        pipeline._chunk_code("a", chunk_size=0, overlap=0)


def test_complexity_levels():
    pipeline = AnalysisPipeline(mimo_client=None, token_tracker=None)  # type: ignore[arg-type]
    simple = "pragma solidity ^0.8.0;\ncontract A {}"
    c = pipeline._estimate_complexity(simple)
    assert c["level"] == "low"

    complex_code = (
        "pragma solidity ^0.8.0;\ncontract B {\n"
        + "\n".join(f"function f{i}() external {{ x.call(\"\"); }}" for i in range(20))
        + "\n}"
    )
    c2 = pipeline._estimate_complexity(complex_code)
    assert c2["level"] in {"high", "critical"}
