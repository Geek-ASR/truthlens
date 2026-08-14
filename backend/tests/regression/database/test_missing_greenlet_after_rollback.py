"""Failure taxonomy entry #20 (research_paper/main.tex Appendix, and its
research-script recurrence in Section VII): a MissingGreenlet crash from
a stale ORM read after rollback.

Production instance: app/api/routers/reels.py's quick_fact_check(). A
per-claim/per-stage exception handler calls `await db.rollback()`; the
next line's read of an already-loaded ORM attribute (e.g. `reel.id`
inside an f-string, a synchronous access with no `await`) then triggers
an implicit lazy-reload that needs an awaited DB round trip and crashes
with "MissingGreenlet: greenlet_spawn has not been called" instead of
the intended HTTPException. Fixed there by capturing `reel_id = reel.id`
into a plain variable *before* any subsequent rollback in the same
handler (see that file's own comment).

This test reproduces the underlying SQLAlchemy behavior directly against
a real Postgres session (not mocked) to prove the fix pattern actually
works and the bug pattern actually fails, so the fix's rationale is
verified, not just asserted in a comment."""
import pytest
from sqlalchemy import select

from app.db.models import Platform, Reel
from app.db.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_capturing_id_before_rollback_avoids_missing_greenlet():
    """The actual fix pattern: read the attribute into a plain variable
    before rollback, then use the plain variable afterward."""
    async with AsyncSessionLocal() as db:
        reel = Reel(source_url="https://instagram.com/reel/greenlet-fix-test", platform=Platform.instagram)
        db.add(reel)
        await db.commit()
        await db.refresh(reel)

        reel_id = reel.id  # captured BEFORE rollback -- the fix

        await db.rollback()

        # Using the plain variable never touches the (now-expired) ORM
        # object at all -- this is exactly why the fix works, and this
        # assertion would still pass even if SQLAlchemy's expiry
        # behavior changed, since it never re-reads from `reel`.
        assert reel_id is not None
        result = await db.execute(select(Reel).where(Reel.id == reel_id))
        assert result.scalar_one().source_url == "https://instagram.com/reel/greenlet-fix-test"


@pytest.mark.asyncio
async def test_reading_expired_attribute_synchronously_after_rollback_raises_missing_greenlet():
    """The bug pattern this fix replaced: reading the ORM attribute
    itself (not a pre-captured variable) after a rollback. Confirms the
    failure this test file's sibling proves is actually fixed is real,
    not hypothetical -- the exact exception message this project's own
    fix comment names."""
    from sqlalchemy.exc import MissingGreenlet

    async with AsyncSessionLocal() as db:
        reel = Reel(source_url="https://instagram.com/reel/greenlet-bug-test", platform=Platform.instagram)
        db.add(reel)
        await db.commit()
        await db.refresh(reel)

        # Force every attribute to expire, matching what a real
        # rollback() does to already-loaded objects in the session.
        db.expire(reel)

        with pytest.raises(MissingGreenlet):
            # Synchronous access to an expired attribute outside of an
            # awaited context -- this is the crash the fix avoids by
            # never doing this (reading `reel.id` this way, unguarded,
            # inside an f-string was the real production bug).
            str(reel.id)
