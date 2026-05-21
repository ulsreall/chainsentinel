"""Multi-Agent Smart Contract Analysis Pipeline.

Orchestrates 4 specialized AI agents (vuln scanner, gas optimizer, logic auditor,
report generator) to perform a comprehensive smart contract audit.

Phase 1 (parallel): vulnerability_scanner, gas_optimizer, logic_auditor
Phase 2 (sequential): report_generator (consumes phase 1 output)
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from app.core.logging import logger
from app.core.token_tracker import TokenTracker
from app.services.mimo_client import MiMoClient


class AnalysisPipeline:
    """Orchestrates multi-agent smart contract analysis."""

    AGENTS = [
        {"id": "vuln_scan", "role": "vulnerability_scanner", "priority": 1},
        {"id": "gas_opt", "role": "gas_optimizer", "priority": 2},
        {"id": "logic_audit", "role": "logic_auditor", "priority": 2},
        {"id": "report_gen", "role": "report_generator", "priority": 3},
    ]

    def __init__(self, mimo_client: MiMoClient, token_tracker: TokenTracker) -> None:
        self.client = mimo_client
        self.tracker = token_tracker

    def _chunk_code(
        self, code: str, chunk_size: int = 200, overlap: int = 20
    ) -> list[str]:
        """Split code into overlapping chunks for analysis."""
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be in [0, chunk_size)")

        lines = code.split("\n")
        chunks: list[str] = []
        i = 0
        step = chunk_size - overlap
        while i < len(lines):
            end = min(i + chunk_size, len(lines))
            chunk = "\n".join(lines[i:end])
            if chunk.strip():
                chunks.append(chunk)
            if end >= len(lines):
                break
            i += step
        return chunks

    def _estimate_complexity(self, code: str) -> dict[str, Any]:
        """Estimate contract complexity for resource allocation."""
        lines = code.split("\n")
        loc = len([ln for ln in lines if ln.strip() and not ln.strip().startswith("//")])
        functions = code.count("function ")
        modifiers = code.count("modifier ")
        events = code.count("event ")
        mappings = code.count("mapping(")
        loops = code.count("for (") + code.count("while (")
        external_calls = (
            code.count(".call(") + code.count(".delegatecall(") + code.count(".send(")
        )
        has_assembly = "assembly" in code

        complexity_score = (
            loc * 0.1
            + functions * 2
            + modifiers * 3
            + loops * 4
            + external_calls * 5
            + (10 if has_assembly else 0)
        )

        if complexity_score < 20:
            level = "low"
        elif complexity_score < 60:
            level = "medium"
        elif complexity_score < 120:
            level = "high"
        else:
            level = "critical"

        return {
            "score": round(complexity_score, 1),
            "level": level,
            "loc": loc,
            "functions": functions,
            "modifiers": modifiers,
            "events": events,
            "mappings": mappings,
            "loops": loops,
            "external_calls": external_calls,
            "has_assembly": has_assembly,
            "chunks": max(1, loc // 200),
        }

    async def run_agent(
        self,
        agent_role: str,
        code: str,
        context: str = "",
        analysis_id: str = "",
    ) -> dict[str, Any]:
        """Run a single analysis agent."""
        result = await self.client.analyze_code(
            code=code, agent_role=agent_role, context=context
        )
        tokens = result.get("tokens", {}).get("total", 0)
        self.tracker.record_usage(tokens, agent=agent_role, analysis_id=analysis_id)

        return {
            "agent": agent_role,
            "result": result.get("content", "") or "",
            "tokens_used": tokens,
            "elapsed": result.get("elapsed_seconds", 0),
            "error": result.get("error"),
        }

    async def _run_agent_over_chunks(
        self,
        agent_role: str,
        chunks: list[str],
        contract_name: str,
        loc: int,
        analysis_id: str,
    ) -> dict[str, Any]:
        """Run a single agent across all chunks in parallel, then aggregate."""
        tasks = [
            self.run_agent(
                agent_role,
                chunk,
                context=f"Chunk {i + 1}/{len(chunks)} of {contract_name} ({loc} lines total)",
                analysis_id=analysis_id,
            )
            for i, chunk in enumerate(chunks)
        ]
        chunk_results = await asyncio.gather(*tasks, return_exceptions=False)

        combined = "\n\n---\n\n".join(r["result"] for r in chunk_results if r["result"])
        return {
            "agent": agent_role,
            "result": combined,
            "tokens_used": sum(r["tokens_used"] for r in chunk_results),
            "elapsed": sum(r["elapsed"] for r in chunk_results),
            "chunks_analyzed": len(chunks),
            "errors": [r["error"] for r in chunk_results if r.get("error")],
        }

    async def analyze(self, code: str, contract_name: str = "Unknown") -> dict[str, Any]:
        """Run the full multi-agent analysis pipeline."""
        analysis_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        logger.info("[%s] Starting analysis of %s", analysis_id, contract_name)

        complexity = self._estimate_complexity(code)
        chunks = self._chunk_code(code)

        # Phase 1: run vuln/gas/logic in TRUE parallel (across agents AND chunks)
        phase1_agents = [a for a in self.AGENTS if a["priority"] <= 2]
        if len(chunks) > 1:
            phase1_coros = [
                self._run_agent_over_chunks(
                    a["role"], chunks, contract_name, complexity["loc"], analysis_id
                )
                for a in phase1_agents
            ]
        else:
            phase1_coros = [
                self.run_agent(a["role"], code, "", analysis_id) for a in phase1_agents
            ]
        phase1_results = await asyncio.gather(*phase1_coros)

        for r in phase1_results:
            r.setdefault("chunks_analyzed", len(chunks) if len(chunks) > 1 else 1)

        # Phase 2: report synthesis (sequential, depends on phase 1)
        vuln_result = next(
            (r for r in phase1_results if r["agent"] == "vulnerability_scanner"), {}
        )
        gas_result = next(
            (r for r in phase1_results if r["agent"] == "gas_optimizer"), {}
        )
        logic_result = next(
            (r for r in phase1_results if r["agent"] == "logic_auditor"), {}
        )

        report_context = (
            f"## Vulnerability Scan Results\n{vuln_result.get('result', 'N/A')}\n\n"
            f"## Gas Optimization Results\n{gas_result.get('result', 'N/A')}\n\n"
            f"## Logic Audit Results\n{logic_result.get('result', 'N/A')}\n\n"
            f"## Contract Metadata\n{complexity}"
        )
        report_result = await self.run_agent(
            "report_generator", code, report_context, analysis_id
        )

        total_tokens = sum(r.get("tokens_used", 0) for r in phase1_results) + report_result.get(
            "tokens_used", 0
        )
        total_elapsed = time.time() - start_time

        self.tracker.record_analysis()
        logger.info(
            "[%s] Done: %d tokens in %.2fs", analysis_id, total_tokens, total_elapsed
        )

        return {
            "analysis_id": analysis_id,
            "contract_name": contract_name,
            "complexity": complexity,
            "pipeline": {
                "vulnerability_scan": vuln_result,
                "gas_optimization": gas_result,
                "logic_audit": logic_result,
                "report_synthesis": report_result,
            },
            "report": report_result.get("result", ""),
            "total_tokens_used": total_tokens,
            "total_elapsed_seconds": round(total_elapsed, 2),
            "agents_used": 4,
            "chunks_processed": len(chunks),
        }
