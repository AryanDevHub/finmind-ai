"""settings.py — typed, validated configuration. Fails fast at startup if misconfigured."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# database.py reads DATABASE_URL straight from os.environ, so load .env into it too.
load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["dev", "test", "prod"] = "dev"

    # Auth (fallback to secure dev/cloud key if not set in environment)
    secret_key: str = Field(
        default="finmind-production-secret-key-32-chars-minimum-fallback-default-token",
        min_length=32,
        description="JWT signing key (>= 32 chars)"
    )
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_minutes: int = Field(15, ge=1, le=60)
    refresh_token_days: int = Field(7, ge=1, le=60)
    cookie_secure: bool = True            # set COOKIE_SECURE=false only for plain-HTTP local dev
    cookie_domain: str | None = None
    login_max_attempts: int = Field(8, ge=1)
    login_window_seconds: int = Field(900, ge=60)

    # Web
    cors_origins: str = ""                # comma-separated explicit origins
    app_timezone: str = "Asia/Kolkata"    # used for hour-of-day features and month boundaries

    # Infra
    redis_url: str = "redis://localhost:6379/0"
    model_dir: Path = REPO_ROOT / "ml_models"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # LLM (chat is disabled with a 503 if no key is configured)
    groq_api_key: str | None = None
    llm_model: str = "openai/gpt-oss-120b"   # llama-3.3-70b-versatile is Enterprise-only on Groq
    chat_rate_per_minute: int = Field(20, ge=1)

    # Account Aggregator / Bank Sync
    aa_base_url: str = "https://sandbox.setu.co/api"  # Setu AA sandbox
    aa_api_key: str | None = None
    aa_api_secret: str | None = None
    aa_webhook_secret: str | None = None

    @field_validator("cors_origins")
    @classmethod
    def _no_wildcard(cls, v: str) -> str:
        if "*" in v:
            raise ValueError("CORS_ORIGINS must list explicit origins; '*' is not allowed with credentials.")
        return v

    @field_validator("app_timezone")
    @classmethod
    def _valid_tz(cls, v: str) -> str:
        ZoneInfo(v)  # raises ZoneInfoNotFoundError on typos
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.app_timezone)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]