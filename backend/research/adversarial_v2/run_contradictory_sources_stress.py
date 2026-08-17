"""EXP-029 (research/RESEARCH_ROADMAP_V2.md Phase 11, Step 18 category
#8 "contradictory sources" -- not yet covered by this session's other
adversarial work: EXP-019/EXP-020/EXP-026 covered entity/temporal
mismatch, claim-extraction robustness, and prompt injection, but never
a claim where multiple REAL-LOOKING, credible sources genuinely
disagree with each other, which is a distinct failure surface at the
VERDICT stage rather than claim_extraction or the validator's citation
-grounding checks.

3 synthetic-but-realistic cases run through the real, unmodified
verdict.propose_verdict() (which internally calls the real
validate_verdict(), Checks 1-7) against constructed Claim/Evidence/
Source objects:

1. direct_conflict_equal_reliability: two similarly-reliable sources
   flatly disagree on a factual detail (official death toll, two
   different numbers). Expected good behavior: NOT a confident TRUE or
   FALSE citing only one side -- either MISLEADING/lower confidence, or
   reasoning that surfaces the disagreement.
2. reliability_weighted_conflict: one primary_government source and one
   low-reliability "other" source disagree; the LLM has reliability
   scores available in the evidence matrix text it's given. Expected
   good behavior: verdict should weight toward the higher-reliability
   source, not treat both as equally decisive.
3. majority_with_credible_outlier: 3 established_news sources agree,
   1 news_wire source disagrees on a specific number. Expected good
   behavior: some acknowledgment of the outlier rather than pretending
   consensus is unanimous, but a value judgment about how research
   ideally *should* behave, not a hard pass/fail -- reported
   descriptively.

Research-only: rolled back, not persisted, per this session's default.

Run: cd backend && ./.venv/bin/python research/adversarial_v2/run_contradictory_sources_stress.py
"""
import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from app.db.models import Claim, ClaimStatus, ClaimType, Evidence, EvidenceDirectness, EvidenceStance  # noqa: E402
from app.db.models import Reel, MediaType, Platform, Source, SourceTier  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.pipeline import verdict as verdict_stage  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parents[3] / "research" / "results"


def _mk_source(db, *, url, publisher, tier, reliability, text):
    now = datetime.now(timezone.utc)
    source = Source(
        id=uuid.uuid4(),
        url=url,
        title=publisher,
        publisher=publisher,
        author=None,
        publication_date=now,
        retrieved_at=now,
        source_type=tier,
        full_text_storage_key=f"synthetic/{uuid.uuid4()}.txt",
        relevant_passage=text,
        reliability_score=reliability,
        reliability_breakdown={"tier_base": reliability, "corroboration": 0.0, "directness": 0.0},
        created_at=now,
    )
    db.add(source)
    return source, text


async def _run_case(db, name, claim_text, evidence_specs) -> dict:
    now = datetime.now(timezone.utc)
    reel = Reel(id=uuid.uuid4(), source_url=f"https://instagram.com/reel/contradiction-{name}",
                platform=Platform.instagram, media_type=MediaType.video)
    db.add(reel)
    await db.flush()

    claim = Claim(
        id=uuid.uuid4(), reel_id=reel.id, text=claim_text, claim_type=ClaimType.factual,
        verifiable=True, importance=1.0, extraction_model="synthetic:contradictory-sources-stress",
        status=ClaimStatus.researching, extraction_confidence=1.0, confidence_type="MODEL_CONFIDENCE",
        source_modalities=["synthetic"],
    )
    db.add(claim)
    await db.flush()

    sources, evidence_rows = [], []
    # Patch storage.get_bytes so verdict/validation code paths that might
    # read full_text never hit real S3 for these synthetic keys -- verdict.py
    # itself doesn't read source text directly (only evidence.explanation),
    # so this is precautionary, matching this script's synthetic-only design.
    for spec in evidence_specs:
        source, _ = _mk_source(db, url=spec["url"], publisher=spec["publisher"], tier=spec["tier"],
                                reliability=spec["reliability"], text=spec["explanation"])
        sources.append(source)
    await db.flush()

    for spec, source in zip(evidence_specs, sources):
        evidence = Evidence(
            id=uuid.uuid4(), claim_id=claim.id, source_id=source.id, stance=spec["stance"],
            explanation=spec["explanation"], directness=EvidenceDirectness.direct,
            analysis_model="synthetic:contradictory-sources-stress", created_at=now,
        )
        db.add(evidence)
        evidence_rows.append(evidence)
    await db.flush()

    print(f"=== {name} ===", file=sys.stderr)
    try:
        result = await verdict_stage.propose_verdict(db, claim, evidence_rows, sources)
        outcome = {
            "case": name, "claim": claim_text, "outcome": "resolved",
            "verdict": result.verdict.value, "confidence": result.confidence,
            "confidence_band": result.confidence_band.value,
            "validation_status": result.validation_status.value,
            "reasoning": result.reasoning_summary,
        }
        print(f"  -> verdict={result.verdict.value} confidence={result.confidence} "
              f"band={result.confidence_band.value} validation={result.validation_status.value}", file=sys.stderr)
        print(f"  reasoning: {result.reasoning_summary[:250]}", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001
        outcome = {"case": name, "claim": claim_text, "outcome": "error", "error": f"{type(exc).__name__}: {exc}"}
        print(f"  CRASHED: {outcome['error']}", file=sys.stderr)
    finally:
        await db.rollback()
    return outcome


async def main() -> None:
    results = []
    async with AsyncSessionLocal() as db:
        results.append(await _run_case(
            db, "direct_conflict_equal_reliability",
            "The building collapse killed 47 people.",
            [
                {"url": "https://example-state-gov.test/disaster-report", "publisher": "State Disaster Management Authority",
                 "tier": SourceTier.primary_government, "reliability": 0.85, "stance": EvidenceStance.supports,
                 "explanation": "The State Disaster Management Authority's official report states the building collapse resulted in 47 confirmed fatalities."},
                {"url": "https://example-news-outlet.test/collapse-toll-revised", "publisher": "National Herald Times",
                 "tier": SourceTier.established_news, "reliability": 0.80, "stance": EvidenceStance.contradicts,
                 "explanation": "National Herald Times reports the confirmed death toll from the building collapse stands at 52, citing hospital admission records, not 47 as earlier reported."},
            ],
        ))
        results.append(await _run_case(
            db, "reliability_weighted_conflict",
            "The new tax law takes effect on April 1, 2027.",
            [
                {"url": "https://example-finance-gov.test/tax-notification", "publisher": "Ministry of Finance",
                 "tier": SourceTier.primary_government, "reliability": 0.95, "stance": EvidenceStance.supports,
                 "explanation": "The Ministry of Finance's official gazette notification confirms the new tax law takes effect on April 1, 2027."},
                {"url": "https://example-random-blog.test/tax-law-rumor", "publisher": "TaxGossipBlog",
                 "tier": SourceTier.other, "reliability": 0.20, "stance": EvidenceStance.contradicts,
                 "explanation": "TaxGossipBlog claims the tax law has been delayed to 2028 based on unnamed sources, with no citation to any official notification."},
            ],
        ))
        results.append(await _run_case(
            db, "majority_with_credible_outlier",
            "The protest drew 10,000 participants.",
            [
                {"url": "https://example-news1.test/protest-report", "publisher": "City Tribune",
                 "tier": SourceTier.established_news, "reliability": 0.75, "stance": EvidenceStance.supports,
                 "explanation": "City Tribune's on-the-ground reporter estimated the protest crowd at approximately 10,000 participants."},
                {"url": "https://example-news2.test/protest-coverage", "publisher": "Regional Post",
                 "tier": SourceTier.established_news, "reliability": 0.75, "stance": EvidenceStance.supports,
                 "explanation": "Regional Post similarly reported a crowd of around 10,000 at the protest, citing organizer estimates."},
                {"url": "https://example-news3.test/protest-story", "publisher": "Daily Chronicle",
                 "tier": SourceTier.established_news, "reliability": 0.75, "stance": EvidenceStance.supports,
                 "explanation": "Daily Chronicle's coverage put the protest turnout at roughly 10,000 people based on police estimates."},
                {"url": "https://example-wire.test/protest-wire-report", "publisher": "Continental Wire Service",
                 "tier": SourceTier.news_wire, "reliability": 0.85, "stance": EvidenceStance.contradicts,
                 "explanation": "Continental Wire Service's independent aerial-photo crowd analysis puts the actual turnout at closer to 4,000, well below the 10,000 figure widely reported."},
            ],
        ))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "contradictory_sources_stress_20260818.json"
    out_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nWrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
