"""Wires the individual pipeline stage modules into the two operations the
API exposes (docs/ROADMAP.md Phase 1 & 2):

  analyze_reel()       — transcript -> OCR -> vision -> claims -> (per
                          verifiable claim) research -> evidence -> verdict
  build_fact_check()   — duplicate check -> content generation ->
                          4-slide render -> FactCheck row, ready for
                          human review

Kept as plain function composition (no hidden framework) so each stage's
audit trail stays easy to follow end to end."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateFactCheckError, ResearchFailedError
from app.db.models import Claim, ClaimStatus, Evidence, FactCheck, FactCheckStatus, Reel, Source, Verdict
from app.pipeline import (
    claim_extraction,
    content_generation,
    duplicate_detection,
    evidence_analysis,
    ingestion,
    ocr,
    research_planning,
    search_fetch,
    slide_generation,
    transcription,
    verdict as verdict_stage,
    vision_context,
)
from app.services.search.factory import get_search_provider
from app.services.storage.s3 import get_storage_client


async def analyze_reel(db: AsyncSession, reel: Reel) -> Reel:
    storage = get_storage_client()

    if reel.media_storage_key:
        video_bytes = storage.get_bytes(reel.media_storage_key)
        audio_path, frame_paths = ingestion.extract_media_artifacts(video_bytes)
        await transcription.transcribe_reel(db, reel, audio_path)
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


async def build_fact_check(db: AsyncSession, claim: Claim) -> FactCheck:
    # Publication gate: research infrastructure failure must never reach a
    # publishable fact-check, even indirectly. This claim has no Verdict
    # row at all (analyze_reel skipped verdict generation on
    # ResearchFailedError) — "no verdict yet" below would already catch
    # it, but checking status explicitly gives a much clearer error than
    # a generic "no verdict" message when the real problem is
    # infrastructure, not an unresearched claim.
    if claim.status == ClaimStatus.research_failed:
        raise ValueError(
            "Research failed for this claim (search infrastructure error) — cannot build a "
            "fact-check from it. This is not the same as UNVERIFIED. Retry research (fix the "
            "search backend, then re-run analyze) before building a fact-check."
        )

    reel_result = await db.execute(select(Reel).where(Reel.id == claim.reel_id))
    reel = reel_result.scalar_one()

    verdict_result = await db.execute(
        select(Verdict).where(Verdict.claim_id == claim.id).order_by(Verdict.created_at.desc())
    )
    current_verdict = verdict_result.scalars().first()
    if current_verdict is None:
        raise ValueError("Claim has no verdict yet; run analyze_reel/research first.")

    duplicate = await duplicate_detection.find_duplicate(db, reel, claim)

    evidence_result = await db.execute(select(Evidence).where(Evidence.claim_id == claim.id))
    evidence_rows = list(evidence_result.scalars().all())
    source_ids = [e.source_id for e in evidence_rows]
    sources: list[Source] = []
    if source_ids:
        sources_result = await db.execute(select(Source).where(Source.id.in_(source_ids)))
        sources = list(sources_result.scalars().all())

    fact_check = FactCheck(
        reel_id=reel.id,
        primary_claim_id=claim.id,
        covered_claim_ids=[],
        current_verdict_id=current_verdict.id,
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

    generated, caption, caption_sources = await content_generation.generate_content(
        db, claim=claim, verdict=current_verdict, reel=reel, evidence_rows=evidence_rows, sources=sources
    )
    await slide_generation.generate_slides(
        db,
        fact_check=fact_check,
        claim=claim,
        verdict=current_verdict,
        reel=reel,
        generated=generated,
        caption_sources=caption_sources,
    )

    fact_check.caption_text = caption
    fact_check.status = FactCheckStatus.ready_for_review
    await db.flush()
    return fact_check
