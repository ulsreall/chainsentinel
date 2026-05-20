"""Application configuration."""

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    MIMO_API_KEY: str = os.getenv("MIMO_API_KEY", "")
    MIMO_BASE_URL: str = os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
    MIMO_MODEL: str = os.getenv("MIMO_MODEL", "mimo-v2.5-pro")

    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")

    # Token management
    DAILY_TOKEN_BUDGET: int = 10_000_000  # 10M tokens/day target
    MAX_CONCURRENT_ANALYSES: int = 5
    MAX_CONTRACT_SIZE_KB: int = 500

    # Analysis pipeline config
    AGENTS_PER_ANALYSIS: int = 4  # Number of AI agents per contract audit
    CHUNK_SIZE_LINES: int = 200  # Lines per analysis chunk
    OVERLAP_LINES: int = 20  # Overlap between chunks


settings = Settings()
