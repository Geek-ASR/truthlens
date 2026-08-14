import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("FIELD_ENCRYPTION_KEY", "YmyUibCkJHSGXz6H0PkP2aQJR173CnAQsXgAC25nSN8=")
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://truthlens:truthlens@localhost:5432/truthlens"
)


@pytest.fixture
def new_uuid():
    return uuid.uuid4


@pytest.fixture(autouse=True)
async def _dispose_engine_between_tests():
    """pytest-asyncio gives each test function its own event loop, but
    app.db.session builds one module-level asyncpg pool at import time.
    Disposing it before each test forces fresh connections bound to the
    current loop instead of reusing one tied to a closed loop."""
    from app.db.session import engine

    await engine.dispose()
    yield


@pytest.fixture(autouse=True)
def _reset_gemini_quota_state():
    """app.services.ai.gemini_quota.get_gemini_provider() is a
    process-lifetime singleton (deliberately, so cooldown/call-cap state
    is shared across real call sites within one run) — reset it before
    every test so one test's simulated quota exhaustion or call count
    can never leak into another's assertions."""
    from app.services.ai.gemini_quota import reset_gemini_provider_for_tests

    reset_gemini_provider_for_tests()
    yield
    reset_gemini_provider_for_tests()
