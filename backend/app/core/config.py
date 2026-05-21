"""Application configuration."""

import os
from dataclasses import dataclass, field


def _csv_env(name: str, default: str = "") -> list[str]:
    """Parse comma-separated env var into a list of stripped, non-empty strings."""
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass
class Settings:
    # MiMo / LLM provider
    MIMO_API_KEY: str = os.getenv("MIMO_API_KEY", "")
    MIMO_BASE_URL: str = os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
    MIMO_MODEL: str = os.getenv("MIMO_MODEL", "mimo-v2.5-pro")

    # Application
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")

    # Security
    # Comma-separated list of allowed origins. Use "*" only in dev.
    ALLOWED_ORIGINS: list[str] = field(
        default_factory=lambda: _csv_env("ALLOWED_ORIGINS", "http://localhost:3000")
    )
    # Comma-separated API keys. If empty, auth is disabled (dev mode warning emitted).
    API_KEYS: list[str] = field(default_factory=lambda: _csv_env("API_KEYS", ""))
    # Skip auth header check entirely (development convenience).
    AUTH_DISABLED: bool = os.getenv("AUTH_DISABLED", "false").lower() == "true"

    # Rate limiting
    RATE_LIMIT_ANALYZE: str = os.getenv("RATE_LIMIT_ANALYZE", "10/minute")
    RATE_LIMIT_BATCH: str = os.getenv("RATE_LIMIT_BATCH", "2/minute")
    RATE_LIMIT_CHAT: str = os.getenv("RATE_LIMIT_CHAT", "30/minute")
    RATE_LIMIT_STATS: str = os.getenv("RATE_LIMIT_STATS", "60/minute")

    # Token management
    DAILY_TOKEN_BUDGET: int = int(os.getenv("DAILY_TOKEN_BUDGET", "10000000"))
    BUDGET_ENFORCE: bool = os.getenv("BUDGET_ENFORCE", "true").lower() == "true"
    MAX_CONCURRENT_ANALYSES: int = int(os.getenv("MAX_CONCURRENT_ANALYSES", "5"))

    # Upload limits
    MAX_CONTRACT_SIZE_KB: int = int(os.getenv("MAX_CONTRACT_SIZE_KB", "500"))
    MAX_CONTRACT_LOC: int = int(os.getenv("MAX_CONTRACT_LOC", "5000"))

    # Analysis pipeline config
    AGENTS_PER_ANALYSIS: int = 4
    CHUNK_SIZE_LINES: int = int(os.getenv("CHUNK_SIZE_LINES", "200"))
    OVERLAP_LINES: int = int(os.getenv("OVERLAP_LINES", "20"))

    # Storage paths (relative-friendly, container-friendly)
    DATA_DIR: str = os.getenv(
        "DATA_DIR",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data")),
    )

    @property
    def TOKEN_LOG_FILE(self) -> str:
        return os.path.join(self.DATA_DIR, "token_usage.jsonl")

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"


settings = Settings()
