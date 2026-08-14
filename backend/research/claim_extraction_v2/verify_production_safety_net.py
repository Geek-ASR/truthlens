"""EXP-009 follow-up: EXP-009 tested claim extraction via raw
OllamaProvider only (no Gemini fallback, deliberately, to isolate the
prompt variable) and found a high real-world failure/empty-output rate.
This script asks the actual next question: does PRODUCTION's real
extract_claims() -- with the full stack EXP-009 bypassed (the
quality-retry Gemini escalation, the empty-text filter, and this
session's new deduplication) -- actually recover on the same items that
failed raw?

Uses the real GEMINI_API_KEY already configured in this environment.
This is exactly the "genuinely necessary" cross-check case: verifying
the actual production safety net EXP-009's finding is *about*, which by
definition cannot be answered by another local-only test. Runs inside a
transaction that is always rolled back -- no claim rows are left
attached to the live benchmark-tagged reel.

Run: ./.venv/bin/python research/claim_extraction_v2/verify_production_safety_net.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from sqlalchemy import select  # noqa: E402

from app.db.models import Reel  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.pipeline.claim_extraction import extract_claims  # noqa: E402

# The item where raw Ollama (no fallback) failed schema validation
# outright in EXP-009 (4 out-of-range field values).
_TARGET_URL = "https://www.instagram.com/reel/DbNU9W7xA9P/"


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Reel).where(Reel.source_url == _TARGET_URL).limit(1))
        reel = result.scalars().first()
        if reel is None:
            print(f"No reel found for {_TARGET_URL}")
            return

        try:
            claims = await extract_claims(db, reel)
            print(f"extract_claims() succeeded: {len(claims)} claim(s) persisted (pre-rollback)")
            for c in claims:
                print(f"  - text={c.text!r}")
                print(f"    claim_type={c.claim_type.value}, verifiable={c.verifiable}, "
                      f"importance={c.importance}, extraction_confidence={c.extraction_confidence}, "
                      f"confidence_type={c.confidence_type}, verifiability={c.verifiability}, "
                      f"source_modalities={c.source_modalities}, extraction_model={c.extraction_model}")
        except Exception as exc:
            print(f"extract_claims() FAILED even with the full production stack: {type(exc).__name__}: {exc}")
        finally:
            # Never persist -- this is a verification run against a real
            # benchmark-tagged reel, not a real ingestion.
            await db.rollback()
            print("\n(transaction rolled back -- nothing persisted)")


if __name__ == "__main__":
    asyncio.run(main())
