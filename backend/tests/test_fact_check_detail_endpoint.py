"""Regression test for a real bug found live: FactCheck.overall_verdict_label
and overall_verdict_reasoning were added to the DB model and to the
FactCheckDetail response schema (backend/app/db/models.py,
backend/app/schemas/fact_check.py), but _load_fact_check_detail
(backend/app/api/routers/fact_checks.py) was never updated to pass them
into the constructor. Pydantic then raised a validation error for every
single GET /api/fact-checks/{id} call — a 500 that only showed up by
actually calling the HTTP endpoint, not by checking the pipeline output
or the database directly (which is how the field was verified earlier
and how the gap was missed)."""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import Claim, ClaimType, FactCheck, FactCheckStatus, Platform, Reel, User, UserRole
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


@pytest.fixture
async def fact_check_with_overall_verdict():
    async with AsyncSessionLocal() as db:
        reel = Reel(source_url="https://example.test/p/abc123/", platform=Platform.instagram)
        db.add(reel)
        await db.flush()

        claim = Claim(reel_id=reel.id, text="Example claim.", claim_type=ClaimType.factual, verifiable=True)
        db.add(claim)
        await db.flush()

        fact_check = FactCheck(
            reel_id=reel.id,
            primary_claim_id=claim.id,
            status=FactCheckStatus.ready_for_review,
            overall_verdict_label="MOSTLY_TRUE",
            overall_verdict_reasoning="Two of three claims checked out; one was unverifiable.",
        )
        db.add(fact_check)
        await db.commit()
        fact_check_id = fact_check.id
    yield fact_check_id
    async with AsyncSessionLocal() as db:
        fc = (await db.execute(select(FactCheck).where(FactCheck.id == fact_check_id))).scalar_one_or_none()
        if fc:
            await db.delete(fc)
            await db.commit()
        claim_row = (await db.execute(select(Claim).where(Claim.id == claim.id))).scalar_one_or_none()
        if claim_row:
            await db.delete(claim_row)
        reel_row = (await db.execute(select(Reel).where(Reel.id == reel.id))).scalar_one_or_none()
        if reel_row:
            await db.delete(reel_row)
        await db.commit()


@pytest.mark.asyncio
async def test_get_fact_check_returns_overall_verdict_fields(admin_user, fact_check_with_overall_verdict):
    email, password = admin_user
    fact_check_id = fact_check_with_overall_verdict
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post("/api/auth/login", json={"email": email, "password": password})
        token = login.json()["access_token"]

        response = await client.get(
            f"/api/fact-checks/{fact_check_id}", headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["overall_verdict_label"] == "MOSTLY_TRUE"
    assert body["overall_verdict_reasoning"] == "Two of three claims checked out; one was unverifiable."
