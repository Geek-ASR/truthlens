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
