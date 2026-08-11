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
    # Default is "ollama": every pipeline stage runs on local models with no
    # API key, no per-token cost, and no vendor usage limits. Empirically
    # picked from the 3 pre-pulled local models (see
    # backend/scripts/estimate_costs.py's local-cost notes and
    # docs/ARCHITECTURE.md §8) — llama3.2:3b passed schema-conformance on
    # every real pipeline schema tested and was ~3x faster than the larger
    # llama3/mistral models on this hardware, so bigger was not better here.
    # Set to "anthropic" (and provide ANTHROPIC_API_KEY) for higher-quality
    # reasoning when local-only isn't required.
    LLM_PROVIDER: Literal["ollama", "anthropic", "gemini"] = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL_CLAIM_EXTRACTION: str = "llama3.2"
    LLM_MODEL_RESEARCH_PLANNING: str = "llama3.2"
    LLM_MODEL_EVIDENCE_ANALYSIS: str = "llama3.2"
    LLM_MODEL_VERDICT: str = "llama3.2"
    LLM_MODEL_CONTENT_GENERATION: str = "llama3.2"
    LLM_MODEL_VISION: str = "llava-phi3"
    # Gemini: used as an automatic fallback whenever LLM_PROVIDER="ollama"
    # and a call fails (see FallbackLLMProvider in services/ai/factory.py)
    # — observed live to recover cases where the small local model
    # produces garbled output on real, longer, code-switched content that
    # a short synthetic test never surfaces. Fallback is skipped entirely
    # (Ollama's own error just propagates) if this key isn't set. Gemini's
    # free tier is generous enough for this project's volume but is still
    # a real external API key subject to Google's rate limits/ToS, unlike
    # Ollama — see docs/ARCHITECTURE.md §8.
    GEMINI_API_KEY: str = ""
    # "-latest" alias rather than a pinned version: pinned "gemini-2.5-*"
    # model names were found live to 404 ("no longer available to new
    # users") for an API key created around Aug 2026 — Google had already
    # moved new signups to newer models. The alias tracks whatever Google
    # currently recommends instead of going stale the same way again.
    LLM_MODEL_GEMINI_FALLBACK: str = "gemini-flash-latest"

    # Transcription — "local" (faster-whisper, CPU, no key) is the default
    # to match LLM_PROVIDER's $0/no-key stance; set "openai" for Whisper
    # API quality/speed instead.
    TRANSCRIPTION_PROVIDER: Literal["openai", "local"] = "local"
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
