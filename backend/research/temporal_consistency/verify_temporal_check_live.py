"""EXP-013 (research/RESEARCH_ROADMAP_V2.md Phase 5): does the new
temporal-consistency check (app/pipeline/validation.py Check 6) actually
fire sensibly against REAL, freshly-fetched evidence -- not just the
synthetic tests/test_validation.py fixtures?

Runs the real research chain (research_planning.plan_research ->
search_fetch.fetch_evidence_sources -> evidence_analysis.analyze_evidence
-> verdict.propose_verdict, which now threads claim.time_reference into
validate_verdict()) against a real claim that already has an explicit,
resolvable time_reference ("August 4, 2026") -- the exact real value
found live in this project's dev data, from the Day 5 audit's own
Durrani/Dipke case (research/VALIDATOR_EVALUATION.md,
tests/test_validation.py's test_downgrades_real_durrani_meeting_case_
from_day5_audit). Also the first live check of whether the DuckDuckGo
publication_date fix (this session, app/services/search/duckduckgo.py)
actually populates real dates on freshly-fetched sources end to end, not
just in the isolated provider-level tests.

Runs inside a transaction that is always rolled back -- no Verdict/
Evidence/Source rows are left attached to the live benchmark-tagged reel.

Run: cd backend && ./.venv/bin/python research/temporal_consistency/verify_temporal_check_live.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from sqlalchemy import select  # noqa: E402

from app.db.models import Claim, ClaimStatus  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.pipeline import evidence_analysis, research_planning, search_fetch  # noqa: E402
from app.pipeline import verdict as verdict_stage  # noqa: E402
from app.services.search.factory import get_search_provider  # noqa: E402

_TARGET_CLAIM_ID = "056f8350-5988-497b-bd31-285728f67821"


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Claim).where(Claim.id == _TARGET_CLAIM_ID))
        claim = result.scalars().first()
        if claim is None:
            print(f"No claim found for id={_TARGET_CLAIM_ID}")
            return

        print(f"claim.text = {claim.text!r}")
        print(f"claim.time_reference = {claim.time_reference!r}")

        try:
            search_provider = get_search_provider()
            queries = await research_planning.plan_research(db, claim)
            print(f"\n{len(queries)} research quer(ies) planned")
            if not queries:
                print("No queries planned -- cannot proceed.")
                return

            sources = await search_fetch.fetch_evidence_sources(db, claim, queries, search_provider)
            print(f"{len(sources)} source(s) fetched")
            for s in sources:
                print(f"  - {s.url} | publication_date={s.publication_date}")

            evidence_rows = await evidence_analysis.analyze_evidence(db, claim, sources) if sources else []
            print(f"{len(evidence_rows)} evidence row(s) analyzed")

            verdict = await verdict_stage.propose_verdict(db, claim, evidence_rows, sources)
            print(f"\nverdict = {verdict.verdict.value}")
            print(f"confidence = {verdict.confidence}")
            print(f"validation_status = {verdict.validation_status.value}")
            print(f"reasoning_summary = {verdict.reasoning_summary}")
        except Exception as exc:
            print(f"FAILED: {type(exc).__name__}: {exc}")
        finally:
            claim.status = ClaimStatus.extracted  # undo any status change plan_research/etc. may have made in-memory
            await db.rollback()
            print("\n(transaction rolled back -- nothing persisted)")


if __name__ == "__main__":
    asyncio.run(main())
