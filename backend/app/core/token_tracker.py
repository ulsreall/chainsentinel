"""Token usage tracking for MiMo API calls."""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from threading import Lock
from typing import Any

from app.core.config import settings
from app.core.logging import logger


class BudgetExceededError(RuntimeError):
    """Raised when daily token budget is exceeded and enforcement is on."""


class TokenTracker:
    """Tracks daily API token consumption across all analysis pipelines."""

    def __init__(self, log_file: str | None = None, daily_budget: int | None = None) -> None:
        self._lock = Lock()
        self._start_time = time.time()
        self._daily_tokens: dict[str, int] = defaultdict(int)
        self._daily_calls: dict[str, int] = defaultdict(int)
        self._analyses: dict[str, int] = defaultdict(int)
        self._agent_tokens: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._history: list[dict[str, Any]] = []

        self.log_file = log_file or settings.TOKEN_LOG_FILE
        self.daily_budget = daily_budget if daily_budget is not None else settings.DAILY_TOKEN_BUDGET
        self._ensure_log_dir()
        self._load_history()

    def _ensure_log_dir(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        except OSError as e:
            logger.warning("Could not create log directory %s: %s", self.log_file, e)

    def _load_history(self) -> None:
        """Replay the JSONL log on startup so stats survive restart."""
        if not os.path.exists(self.log_file):
            return
        loaded = 0
        try:
            with open(self.log_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = entry.get("timestamp", "")
                    day = ts[:10] if ts else self._today()
                    self._daily_tokens[day] += int(entry.get("tokens", 0))
                    self._daily_calls[day] += 1
                    self._agent_tokens[day][entry.get("agent", "general")] += int(
                        entry.get("tokens", 0)
                    )
                    self._history.append(entry)
                    loaded += 1
            logger.info("Loaded %d historical token entries from %s", loaded, self.log_file)
        except OSError as e:
            logger.warning("Could not read token log %s: %s", self.log_file, e)

    @staticmethod
    def _today() -> str:
        return date.today().isoformat()

    def check_budget(self, projected: int = 0) -> None:
        """Raise BudgetExceededError if projected usage would exceed daily budget."""
        if not settings.BUDGET_ENFORCE or self.daily_budget <= 0:
            return
        today = self._today()
        with self._lock:
            current = self._daily_tokens[today]
        if current + projected > self.daily_budget:
            raise BudgetExceededError(
                f"Daily token budget exceeded: {current + projected:,} > {self.daily_budget:,}"
            )

    def record_usage(self, tokens: int, agent: str = "general", analysis_id: str = "") -> None:
        """Record token usage from an API call."""
        if tokens <= 0:
            return
        today = self._today()
        entry = {
            "timestamp": datetime.now().isoformat(),
            "tokens": tokens,
            "agent": agent,
            "analysis_id": analysis_id,
        }
        with self._lock:
            self._daily_tokens[today] += tokens
            self._daily_calls[today] += 1
            self._agent_tokens[today][agent] += tokens
            entry["daily_total"] = self._daily_tokens[today]
            self._history.append(entry)

        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError as e:
            logger.warning("Failed to persist token usage entry: %s", e)

    def record_analysis(self) -> None:
        with self._lock:
            self._analyses[self._today()] += 1

    def get_stats(self) -> dict[str, Any]:
        today = self._today()
        with self._lock:
            tokens_today = self._daily_tokens[today]
            return {
                "date": today,
                "total_tokens_today": tokens_today,
                "api_calls_today": self._daily_calls[today],
                "analyses_completed": self._analyses[today],
                "agent_breakdown": dict(self._agent_tokens[today]),
                "uptime_seconds": int(time.time() - self._start_time),
                "daily_budget": self.daily_budget,
                "budget_used_pct": (
                    round(tokens_today / self.daily_budget * 100, 2)
                    if self.daily_budget > 0
                    else 0.0
                ),
            }

    def get_history(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return self._history[-limit:]

    def get_daily_trend(self, days: int = 7) -> list[dict[str, Any]]:
        today = date.today()
        with self._lock:
            return list(
                reversed(
                    [
                        {
                            "date": (today - timedelta(days=i)).isoformat(),
                            "tokens": self._daily_tokens.get(
                                (today - timedelta(days=i)).isoformat(), 0
                            ),
                            "calls": self._daily_calls.get(
                                (today - timedelta(days=i)).isoformat(), 0
                            ),
                            "analyses": self._analyses.get(
                                (today - timedelta(days=i)).isoformat(), 0
                            ),
                        }
                        for i in range(days)
                    ]
                )
            )
