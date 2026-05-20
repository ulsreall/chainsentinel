"""MiMo API Client — OpenAI-compatible interface for Xiaomi MiMo models."""

import asyncio
import time
from typing import Optional, AsyncGenerator
from openai import AsyncOpenAI


class MiMoClient:
    """Async client for Xiaomi MiMo API (OpenAI-compatible)."""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key or "demo-key",
            base_url=base_url,
            timeout=120.0,
            max_retries=3,
        )

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        system: Optional[str] = None,
    ) -> dict:
        """Single chat completion with token tracking."""
        if system:
            messages = [{"role": "system", "content": system}] + messages

        start = time.time()
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            elapsed = time.time() - start

            usage = response.usage
            return {
                "content": response.choices[0].message.content,
                "tokens": {
                    "prompt": usage.prompt_tokens if usage else 0,
                    "completion": usage.completion_tokens if usage else 0,
                    "total": usage.total_tokens if usage else 0,
                },
                "elapsed_seconds": round(elapsed, 2),
                "model": self.model,
            }
        except Exception as e:
            return {
                "content": None,
                "error": str(e),
                "tokens": {"prompt": 0, "completion": 0, "total": 0},
                "elapsed_seconds": round(time.time() - start, 2),
                "model": self.model,
            }

    async def analyze_code(
        self,
        code: str,
        agent_role: str,
        context: str = "",
        temperature: float = 0.2,
    ) -> dict:
        """Analyze code with a specific agent role."""
        prompts = {
            "vulnerability_scanner": (
                "You are a smart contract vulnerability scanner. Analyze the following Solidity code "
                "for security vulnerabilities. Focus on: reentrancy, integer overflow/underflow, "
                "access control issues, unchecked external calls, frontrunning, oracle manipulation, "
                "flash loan attacks, and logic bugs. Output a structured JSON report."
            ),
            "gas_optimizer": (
                "You are a Solidity gas optimization expert. Analyze the following code for gas "
                "inefficiencies. Identify: storage vs memory usage, loop optimizations, struct packing, "
                "unnecessary SLOAD/SSTORE, calldata vs memory parameters, and assembly opportunities. "
                "Provide specific line-by-line recommendations with estimated gas savings."
            ),
            "logic_auditor": (
                "You are a smart contract logic auditor. Analyze the following code for business logic "
                "flaws: edge cases, state machine issues, MEV vulnerabilities, price manipulation vectors, "
                "governance attacks, timelock bypasses, and economic exploit scenarios. "
                "Provide detailed findings with severity ratings."
            ),
            "report_generator": (
                "You are a security report writer. Given the analysis results from vulnerability scanner, "
                "gas optimizer, and logic auditor, compile a comprehensive professional security audit report. "
                "Include: executive summary, findings by severity, detailed descriptions, "
                "proof-of-concept scenarios where applicable, and remediation recommendations."
            ),
        }

        system_prompt = prompts.get(agent_role, prompts["vulnerability_scanner"])
        if context:
            system_prompt += f"\n\nAdditional context:\n{context}"

        return await self.chat(
            messages=[{"role": "user", "content": f"```solidity\n{code}\n```"}],
            system=system_prompt,
            temperature=temperature,
            max_tokens=4096,
        )

    async def stream_chat(
        self,
        messages: list[dict],
        system: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion."""
        if system:
            messages = [{"role": "system", "content": system}] + messages

        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
            temperature=0.3,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
