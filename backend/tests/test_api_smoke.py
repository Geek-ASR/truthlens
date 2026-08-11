"""End-to-end smoke test against a real Postgres instance (requires
DATABASE_URL to point at a migrated database — see docs/ARCHITECTURE.md).
Exercises health + the auth flow, which is enough to catch import-time
and dependency-wiring regressions across the whole app."""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import User, UserRole
from app.db.session import AsyncSessionLocal
from app.main import app


@pytest.fixture
async def admin_user():
    email = f"test-{uuid.uuid4().hex[:8]}@truthlensapp.io"
    password = "test-password-123"
    async with AsyncSessionLocal() as db:
        user = User(email=email, hashed_password=hash_password(password), role=UserRole.admin)
        db.add(user)
        await db.commit()
        user_id = user.id
    yield email, password
    async with AsyncSessionLocal() as db:
        db_user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if db_user:
            await db.delete(db_user)
            await db.commit()


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_login_and_me_flow(admin_user):
    email, password = admin_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_response = await client.post("/api/auth/login", json={"email": email, "password": password})
        assert login_response.status_code == 200
        access_token = login_response.json()["access_token"]

        me_response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        assert me_response.status_code == 200
        assert me_response.json()["email"] == email


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(admin_user):
    email, _ = admin_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/auth/login", json={"email": email, "password": "wrong-password"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_requires_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/reels")
    assert response.status_code == 401
