"""Application configuration loaded from environment variables."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.local_protected_store import read_local_protected_value


class Settings(BaseSettings):
    """Echora application settings loaded from .env file.

    All sensitive values (passwords, API keys) are read from .env only.
    .env.example contains placeholder values.
    """

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────
    APP_ENV: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: Literal["debug", "info", "warning", "error"] = "info"

    # ── Database ─────────────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+psycopg://postgres:password@127.0.0.1:5432/echora"
    )

    # ── LLM Provider ─────────────────────────────────────────────────
    OPENAI_BASE_URL: str = ""
    OPENAI_MODEL: str = ""
    OPENAI_MODEL_FALLBACKS: str = ""
    OPENAI_API_KEY: str = ""

    # ── Embedding ────────────────────────────────────────────────────
    EMBEDDING_BASE_URL: str = ""
    EMBEDDING_PROVIDER: Literal[
        "auto", "openai_compatible", "dashscope_multimodal", "volcengine_ark"
    ] = "auto"
    DASHSCOPE_EMBEDDING_BASE_URL: str = ""
    ARK_API_KEY: str = ""
    ARK_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
    EMBEDDING_MODEL: str = ""
    EMBEDDING_MODEL_FALLBACKS: str = ""
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_DIMENSIONS: int = 1024
    EMBEDDING_TIMEOUT_SECONDS: int = 60
    EMBEDDING_MAX_RETRIES: int = 1

    # ── Feature Flags (Core conversation defaults) ─────────────────────────────
    ALLOW_MEMORY_CANDIDATES: bool = True
    MEMORY_AUTO_COMMIT_ENABLED: bool = False
    PRESENCE_ENABLED: bool = True
    PRESENCE_SCHEDULER_ENABLED: bool = True
    PRESENCE_SCHEDULER_POLL_SECONDS: int = 15
    PRESENCE_SCHEDULER_LEASE_SECONDS: int = 120
    PRESENCE_SCHEDULER_MAX_ATTEMPTS: int = 3
    TOOL_SCHEDULER_ENABLED: bool = True
    TOOL_SCHEDULER_POLL_SECONDS: int = 10
    QUALITY_FEEDBACK_SCHEDULER_ENABLED: bool = True
    QUALITY_FEEDBACK_SCHEDULER_POLL_SECONDS: int = 10
    QUALITY_FEEDBACK_SCHEDULER_LEASE_SECONDS: int = 120
    QUALITY_FEEDBACK_LOOKBACK_MINUTES: int = 60
    CONVERSATION_TURN_SCHEDULER_ENABLED: bool = True
    CONVERSATION_TURN_SCHEDULER_POLL_SECONDS: int = 1
    CONVERSATION_TURN_SCHEDULER_LEASE_SECONDS: int = 300
    CONVERSATION_TURN_SCHEDULER_BATCH_SIZE: int = 1
    CONVERSATION_POST_TURN_SCHEDULER_POLL_SECONDS: int = 1
    CONVERSATION_POST_TURN_SCHEDULER_LEASE_SECONDS: int = 300
    CONVERSATION_POST_TURN_SCHEDULER_BATCH_SIZE: int = 1
    CONVERSATION_POST_TURN_MAX_ATTEMPTS: int = 3
    DATA_RETENTION_SCHEDULER_ENABLED: bool = True
    DATA_RETENTION_SCHEDULER_POLL_SECONDS: int = 3600
    DATA_RETENTION_SCHEDULER_BATCH_SIZE: int = 2
    TRACE_ENABLED: bool = True
    ALLOW_GROWTH_CANDIDATES: bool = True

    # ── Server ───────────────────────────────────────────────────────
    BACKEND_HOST: str = "127.0.0.1"
    BACKEND_PORT: int = 8010
    FRONTEND_PORT: int = 3000

    # ── CORS ─────────────────────────────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:3000"

    # ── Project paths ────────────────────────────────────────────────
    @property
    def PROJECT_ROOT(self) -> Path:
        """Absolute path to Echora project root."""
        return Path(__file__).resolve().parent.parent.parent.parent.parent

    @property
    def CACHE_DIR(self) -> Path:
        return self.PROJECT_ROOT / ".cache"

    @property
    def LOG_DIR(self) -> Path:
        return self.PROJECT_ROOT / ".logs"

    @property
    def DATA_DIR(self) -> Path:
        return self.PROJECT_ROOT / ".data"

    @property
    def SANDBOX_DIR(self) -> Path:
        return self.PROJECT_ROOT / ".sandbox"


settings = Settings()
database_url_from_environment = settings.DATABASE_URL
_protected_database_url = read_local_protected_value(
    settings.PROJECT_ROOT / ".secrets" / "runtime-configuration.local.json",
    "database_url",
)
if _protected_database_url:
    settings.DATABASE_URL = _protected_database_url
