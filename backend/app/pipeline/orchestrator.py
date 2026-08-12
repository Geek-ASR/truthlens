"""Wires the individual pipeline stage modules into the two operations the
API exposes (docs/ROADMAP.md Phase 1 & 2):

  analyze_reel()       — transcript -> OCR -> vision -> claims -> (per
                          verifiable claim) research -> evidence -> verdict
  build_fact_check()   — duplicate check -> content generation ->
                          4-slide render -> FactCheck row, ready for
                          human review

Kept as plain function composition (no hidden framework) so each stage's
audit trail stays easy to follow end to end."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateFactCheckError, ResearchFailedError
from app.db.models import Claim, ClaimStatus, Evidence, FactCheck, FactCheckStatus, MediaType, Reel, Source, Verdict
from app.pipeline import (
    claim_extraction,
    duplicate_detection,
    evidence_analysis,
    ingestion,
    ocr,
    reel_content,
    research_planning,
    search_fetch,
    slide_generation,
    transcription,
    verdict as verdict_stage,
    vision_context,
)
from app.pipeline.overall_verdict import derive_overall_verdict
from app.services.search.factory import get_search_provider
from app.services.storage.s3 import get_storage_client


async def analyze_reel(db: AsyncSession, reel: Reel) -> Reel:
    storage = get_storage_client()

    if reel.media_storage_key and reel.media_type == MediaType.video:
        video_bytes = storage.get_bytes(reel.media_storage_key)
        audio_path, frame_paths = ingestion.extract_media_artifacts(video_bytes)
        await transcription.transcribe_reel(db, reel, audio_path)
        await ocr.ocr_reel(db, reel, frame_paths)
        await vision_context.analyze_vision_context(db, reel, frame_paths)
    elif reel.media_storage_key and reel.media_type == MediaType.photo:
        # No audio to transcribe. OCR and vision-context analysis both
        # already operate on a plain list of image paths (see their own
        # docstrings) so the single photo is a drop-in one-element
        # "frame_paths" list, not a special case for either function.
        photo_bytes = storage.get_bytes(reel.media_storage_key)
        frame_paths = ingestion.extract_photo_artifact(photo_bytes)
        await ocr.ocr_reel(db, reel, frame_paths)
        await vision_context.analyze_vision_context(db, reel, frame_paths)

    claims = await claim_extraction.extract_claims(db, reel)

    search_provider = get_search_provider()
    for claim in claims:
        if not claim.verifiable:
            continue
        queries = await research_planning.plan_research(db, claim)
        if not queries:
            continue
        try:
            sources = await search_fetch.fetch_evidence_sources(db, claim, queries, search_provider)
        except ResearchFailedError:
            # Infrastructure-level research failure (every query errored) —
            # NEVER silently treated as UNVERIFIED. No Verdict row is
            # created; the claim is marked distinctly so build_fact_check()
            # refuses to build a publishable fact-check from it until
            # research is retried and actually succeeds (docs/CURRENT_ARCHITECTURE.md §10).
            claim.status = ClaimStatus.research_failed
            await db.flush()
            continue
        evidence_rows = await evidence_analysis.analyze_evidence(db, claim, sources) if sources else []
        await verdict_stage.propose_verdict(db, claim, evidence_rows, sources)

    return reel


async def build_reel_fact_check(db: AsyncSession, reel: Reel) -> FactCheck:
    """Builds ONE fact-check covering every verifiable claim on this reel
    — not just a single claim. Overall verdict is derived deterministically
    from the individual (already-validated) claim verdicts
    (app/pipeline/overall_verdict.py), and the carousel is assembled from
    real claim/verdict/source rows (app/pipeline/reel_content.py), not a
    single free-text LLM blob."""
    claims_result = await db.execute(select(Claim).where(Claim.reel_id == reel.id))
    all_claims = list(claims_result.scalars().all())
    verifiable_claims = [c for c in all_claims if c.verifiable]

    if not verifiable_claims:
        raise ValueError("This reel has no verifiable factual claims to build a fact-check from.")

    if all(c.status == ClaimStatus.research_failed for c in verifiable_claims):
        raise ValueError(
            "Research failed for every verifiable claim on this reel (search infrastructure "
            "error) — cannot build a fact-check. This is not the same as UNVERIFIED. Fix the "
            "search backend and re-run analyze before building a fact-check."
        )

    claim_verdict_pairs: list[tuple[Claim, Verdict | None]] = []
    for claim in verifiable_claims:
        verdict_result = await db.execute(
            select(Verdict)
            .where(Verdict.claim_id == claim.id, Verdict.is_current.is_(True))
            .order_by(Verdict.created_at.desc())
        )
        claim_verdict_pairs.append((claim, verdict_result.scalars().first()))

    if all(v is None for _, v in claim_verdict_pairs):
        raise ValueError("No claim on this reel has a verdict yet; run analyze_reel/research first.")

    overall = derive_overall_verdict(claim_verdict_pairs)
    primary_claim = max((c for c, v in claim_verdict_pairs if v is not None), key=lambda c: c.importance)

    duplicate = await duplicate_detection.find_duplicate(db, reel, primary_claim)

    claim_ids = [c.id for c, v in overall.claim_verdicts]
    evidence_result = await db.execute(select(Evidence).where(Evidence.claim_id.in_(claim_ids)))
    all_evidence = list(evidence_result.scalars().all())
    evidence_by_claim: dict = {}
    for e in all_evidence:
        evidence_by_claim.setdefault(e.claim_id, []).append(e)

    source_ids = {e.source_id for e in all_evidence}
    sources_by_id: dict = {}
    if source_ids:
        sources_result = await db.execute(select(Source).where(Source.id.in_(source_ids)))
        sources_by_id = {s.id: s for s in sources_result.scalars().all()}

    # is_current verdict per claim -> current_verdict_id on FactCheck is the primary claim's.
    primary_verdict = next(v for c, v in claim_verdict_pairs if c.id == primary_claim.id)

    fact_check = FactCheck(
        reel_id=reel.id,
        primary_claim_id=primary_claim.id,
        covered_claim_ids=[c.id for c, _ in overall.claim_verdicts],
        current_verdict_id=primary_verdict.id if primary_verdict else None,
        overall_verdict_label=overall.label.value,
        overall_verdict_reasoning=overall.reasoning,
        status=FactCheckStatus.researching,
    )
    db.add(fact_check)
    await db.flush()

    if duplicate is not None:
        fact_check.status = FactCheckStatus.rejected
        fact_check.duplicate_of_fact_check_id = duplicate.fact_check_id
        fact_check.review_notes = f"DUPLICATE — DO NOT PUBLISH. {duplicate.reason}"
        await db.flush()
        raise DuplicateFactCheckError(str(duplicate.fact_check_id), duplicate.reason)

    content = await reel_content.assemble_reel_content(
        reel_creator_handle=reel.creator_handle,
        overall=overall,
        evidence_by_claim=evidence_by_claim,
        sources_by_id=sources_by_id,
    )
    await slide_generation.generate_slides(db, fact_check=fact_check, reel=reel, content=content)

    all_sources_cited = list({s.url: s for s in sources_by_id.values()}.values())
    caption_sources = [
        s for s in all_sources_cited if any(e.stance.value in ("supports", "contradicts") for e in all_evidence if e.source_id == s.id)
    ]
    fact_check.caption_text = _build_reel_caption(reel=reel, content=content, caption_sources=caption_sources)
    fact_check.status = FactCheckStatus.ready_for_review
    await db.flush()
    return fact_check


def _build_reel_caption(*, reel: Reel, content, caption_sources: list[Source]) -> str:
    content_label = "post" if reel.media_type == MediaType.photo else "reel"
    claim_by_claim = "\n".join(
        f"{'✓' if row.icon == '✓' else ('✗' if row.icon == '✗' else '⚠')} {row.claim_text} — "
        f"{row.verdict_label.replace('_', ' ')}"
        for row in content.claim_table
    )
    sources_block = "\n".join(
        f"{i + 1}. {s.publisher or s.title or s.url}\n   {s.url}" for i, s in enumerate(caption_sources[:8])
    ) or "No corroborating sources were found at the time of publication."
    date_str = datetime.now(timezone.utc).strftime("%b %d, %Y")
    return (
        "🔎 FACT CHECK\n\n"
        "CLAIM:\n"
        f'"{content.headline}"\n\n'
        "VERDICT:\n"
        f"{content.overall_verdict_label.replace('_', ' ')}\n\n"
        "WHY:\n"
        f"{content.why_paragraph}\n\n"
        "CLAIM-BY-CLAIM:\n"
        f"{claim_by_claim}\n\n"
        "SOURCES:\n"
        f"{sources_block}\n\n"
        f"ORIGINAL {content_label.upper()}:\n"
        f"{reel.source_url}\n\n"
        f"FACT-CHECKED: {date_str}\n\n"
        "IMPORTANT:\n"
        f"This fact-check evaluates the specific claims made in the referenced {content_label} based on "
        "evidence available at the time of publication.\n\n"
        "#FactCheck #MediaLiteracy #TruthLens"
    )
