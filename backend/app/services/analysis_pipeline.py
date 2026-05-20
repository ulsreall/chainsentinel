"""Multi-Agent Smart Contract Analysis Pipeline.

This is the core engine that orchestrates multiple AI agents to perform
comprehensive smart contract audits. Each agent specializes in a different
aspect of security analysis, consuming significant API tokens per run.

Pipeline stages:
1. Preprocessing — parse, chunk, and prepare contract code
2. Vulnerability Scan — parallel agent scan for known vulnerability patterns
3. Gas Analysis — agent analyzes gas optimization opportunities
4. Logic Audit — agent performs deep business logic analysis
5. Report Synthesis — agent compiles all findings into a professional report
"""

import asyncio
import hashlib
import time
import uuid
from typing import Optional

from app.services.mimo_client import MiMoClient
from app.core.token_tracker import TokenTracker


class AnalysisPipeline:
    """Orchestrates multi-agent smart contract analysis."""

    # Agent definitions with their roles and priorities
    AGENTS = [
        {"id": "vuln_scan", "role": "vulnerability_scanner", "priority": 1},
        {"id": "gas_opt", "role": "gas_optimizer", "priority": 2},
        {"id": "logic_audit", "role": "logic_auditor", "priority": 2},
        {"id": "report_gen", "role": "report_generator", "priority": 3},
    ]

    def __init__(self, mimo_client: MiMoClient, token_tracker: TokenTracker):
        self.client = mimo_client
        self.tracker = token_tracker

    def _chunk_code(self, code: str, chunk_size: int = 200, overlap: int = 20) -> list[str]:
        """Split code into overlapping chunks for analysis."""
        lines = code.split("\n")
        chunks = []
        i = 0
        while i < len(lines):
            end = min(i + chunk_size, len(lines))
            chunk = "\n".join(lines[i:end])
            if chunk.strip():
                chunks.append(chunk)
            i += chunk_size - overlap
        return chunks

    def _estimate_complexity(self, code: str) -> dict:
        """Estimate contract complexity for resource allocation."""
        lines = code.split("\n")
        loc = len([l for l in lines if l.strip() and not l.strip().startswith("//")])
        functions = code.count("function ")
        modifiers = code.count("modifier ")
        events = code.count("event ")
        mappings = code.count("mapping(")
        loops = code.count("for (") + code.count("while (")
        external_calls = code.count(".call(") + code.count(".delegatecall(") + code.count(".send(")
        has_assembly = "assembly" in code

        complexity_score = (
            loc * 0.1 +
            functions * 2 +
            modifiers * 3 +
            loops * 4 +
            external_calls * 5 +
            (10 if has_assembly else 0)
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
    ) -> dict:
        """Run a single analysis agent."""
        result = await self.client.analyze_code(
            code=code,
            agent_role=agent_role,
            context=context,
        )

        # Track token usage
        tokens = result.get("tokens", {}).get("total", 0)
        self.tracker.record_usage(tokens, agent=agent_role, analysis_id=analysis_id)

        return {
            "agent": agent_role,
            "result": result.get("content", ""),
            "tokens_used": tokens,
            "elapsed": result.get("elapsed_seconds", 0),
            "error": result.get("error"),
        }

    async def analyze(self, code: str, contract_name: str = "Unknown") -> dict:
        """
        Run the full multi-agent analysis pipeline.
        
        This generates significant token usage by:
        1. Splitting code into chunks for large contracts
        2. Running 3 specialized analysis agents in parallel
        3. Synthesizing findings with a report generation agent
        4. Each agent processes the full code + chunk context
        """
        analysis_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # Preprocessing
        complexity = self._estimate_complexity(code)
        chunks = self._chunk_code(code)

        # Phase 1: Parallel analysis agents (vuln, gas, logic)
        phase1_agents = [a for a in self.AGENTS if a["priority"] <= 2]
        phase1_tasks = []

        for agent in phase1_agents:
            # For large contracts, analyze each chunk separately then summarize
            if len(chunks) > 1:
                chunk_results = []
                for i, chunk in enumerate(chunks):
                    context = f"Chunk {i+1}/{len(chunks)} of {contract_name} ({complexity['loc']} lines total)"
                    result = await self.run_agent(agent["role"], chunk, context, analysis_id)
                    chunk_results.append(result)

                # Aggregate chunk results
                combined = "\n\n---\n\n".join([r["result"] for r in chunk_results if r["result"]])
                total_tokens = sum(r["tokens_used"] for r in chunk_results)
                total_elapsed = sum(r["elapsed"] for r in chunk_results)

                phase1_tasks.append({
                    "agent": agent["role"],
                    "result": combined,
                    "tokens_used": total_tokens,
                    "elapsed": total_elapsed,
                    "chunks_analyzed": len(chunks),
                })
            else:
                result = await self.run_agent(agent["role"], code, "", analysis_id)
                result["chunks_analyzed"] = 1
                phase1_tasks.append(result)

        # Phase 2: Report synthesis agent
        vuln_result = next((r for r in phase1_tasks if r["agent"] == "vulnerability_scanner"), {})
        gas_result = next((r for r in phase1_tasks if r["agent"] == "gas_optimizer"), {})
        logic_result = next((r for r in phase1_tasks if r["agent"] == "logic_auditor"), {})

        report_context = (
            f"## Vulnerability Scan Results\n{vuln_result.get('result', 'N/A')}\n\n"
            f"## Gas Optimization Results\n{gas_result.get('result', 'N/A')}\n\n"
            f"## Logic Audit Results\n{logic_result.get('result', 'N/A')}\n\n"
            f"## Contract Metadata\n{complexity}"
        )

        report_result = await self.run_agent(
            "report_generator", code, report_context, analysis_id
        )

        # Compile final report
        total_tokens = sum(r.get("tokens_used", 0) for r in phase1_tasks) + report_result.get("tokens_used", 0)
        total_elapsed = time.time() - start_time

        self.tracker.record_analysis()

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
