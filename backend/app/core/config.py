"""Central settings. Fails fast on startup if a required var is missing
rather than silently running with None (see docs/SECURITY.md)."""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = True

    # Database / cache
    DATABASE_URL: str = "postgresql+asyncpg://truthlens:truthlens@localhost:5432/truthlens"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth / crypto
    JWT_SECRET_KEY: str = "change-me-in-.env"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14
    FIELD_ENCRYPTION_KEY: str = ""  # Fernet key, required in production for token encryption

    # LLM providers
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL_CLAIM_EXTRACTION: str = "claude-sonnet-5"
    LLM_MODEL_RESEARCH_PLANNING: str = "claude-sonnet-5"
    LLM_MODEL_EVIDENCE_ANALYSIS: str = "claude-sonnet-5"
    LLM_MODEL_VERDICT: str = "claude-opus-5"
    LLM_MODEL_CONTENT_GENERATION: str = "claude-sonnet-5"
    LLM_MODEL_VISION: str = "claude-sonnet-5"

    # Transcription
    TRANSCRIPTION_PROVIDER: Literal["openai", "local"] = "openai"
    OPENAI_API_KEY: str = ""

    # Search
    SEARCH_PROVIDER: Literal["tavily"] = "tavily"
    SEARCH_API_KEY: str = ""

    # Object storage (S3-compatible)
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "truthlens"
    S3_SECRET_KEY: str = "truthlens-dev-key"
    S3_BUCKET: str = "truthlens-media"
    S3_REGION: str = "us-east-1"
    S3_PUBLIC_BASE_URL: str = "http://localhost:9000/truthlens-media"

    # Meta / Instagram
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    META_GRAPH_API_VERSION: str = "v21.0"
    INSTAGRAM_ACCESS_TOKEN: str = ""

    # Product configuration
    MAX_POSTS_PER_DAY: int = 12
    HUMAN_APPROVAL_MODE: bool = True  # default per product spec §20 — must be explicitly disabled
    MIN_CONFIDENCE_FOR_AUTO_PUBLISH: float = 0.90  # only relevant if HUMAN_APPROVAL_MODE is ever False
    PUBLIC_SITE_BASE_URL: str = "https://truthlens.example"

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
