from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, RequireReviewer
from app.api.routers.fact_checks import _load_fact_check_detail
from app.core.exceptions import DuplicateFactCheckError, ProviderError
from app.db.models import Claim, Evidence, Reel, Verdict
from app.pipeline import evidence_analysis, research_planning, search_fetch
from app.pipeline import verdict as verdict_stage
from app.pipeline.orchestrator import build_reel_fact_check
from app.schemas.claim import ClaimOut
from app.schemas.evidence import EvidenceOut
from app.schemas.fact_check import FactCheckDetail
from app.schemas.verdict import VerdictOut
from app.services.search.factory import get_search_provider

router = APIRouter()


@router.get("/{claim_id}", response_model=ClaimOut)
async def get_claim(claim_id: str, db: DbSession, current_user: RequireReviewer):
    result = await db.execute(select(Claim).where(Claim.id == claim_id))
    claim = result.scalar_one_or_none()
    if claim is None:
        raise HTTPException(404, "Claim not found")
    return claim


@router.get("/{claim_id}/evidence", response_model=list[EvidenceOut])
async def get_claim_evidence(claim_id: str, db: DbSession, current_user: RequireReviewer):
    result = await db.execute(
        select(Evidence).options(selectinload(Evidence.source)).where(Evidence.claim_id == claim_id)
    )
    return list(result.scalars().all())


@router.get("/{claim_id}/verdicts", response_model=list[VerdictOut])
async def get_claim_verdicts(claim_id: str, db: DbSession, current_user: RequireReviewer):
    result = await db.execute(
        select(Verdict).where(Verdict.claim_id == claim_id).order_by(Verdict.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/{claim_id}/research-again", response_model=VerdictOut)
async def research_again(claim_id: str, db: DbSession, current_user: RequireReviewer):
    """The dashboard's "RESEARCH AGAIN" action (product spec §30):
    re-runs planning -> search -> evidence -> verdict from scratch for
    this claim, producing a new (superseding) verdict row."""
    result = await db.execute(select(Claim).where(Claim.id == claim_id))
    claim = result.scalar_one_or_none()
    if claim is None:
        raise HTTPException(404, "Claim not found")
    if not claim.verifiable:
        raise HTTPException(400, "This claim is not marked verifiable and cannot be researched.")

    try:
        queries = await research_planning.plan_research(db, claim)
        search_provider = get_search_provider()
        sources = await search_fetch.fetch_evidence_sources(db, claim, queries, search_provider)
        evidence_rows = await evidence_analysis.analyze_evidence(db, claim, sources) if sources else []
        new_verdict = await verdict_stage.propose_verdict(db, claim, evidence_rows, sources)
    except ProviderError as exc:
        await db.rollback()
        raise HTTPException(502, f"Research failed: {exc}") from exc

    # Mark any prior verdict for this claim as superseded.
    prior = await db.execute(
        select(Verdict).where(
            Verdict.claim_id == claim.id, Verdict.id != new_verdict.id, Verdict.is_current.is_(True)
        )
    )
    for old in prior.scalars().all():
        old.is_current = False
        old.superseded_by_id = new_verdict.id

    await db.commit()
    await db.refresh(new_verdict)
    return new_verdict


@router.post("/{claim_id}/build-fact-check", response_model=FactCheckDetail)
async def build_fact_check_endpoint(claim_id: str, db: DbSession, current_user: RequireReviewer):
    """Phase 2 (product spec §35): generate the 4-slide carousel + caption.
    Builds ONE fact-check covering every verifiable claim on this claim's
    reel (app/pipeline/orchestrator.build_reel_fact_check) — not just this
    single claim — with one overall verdict derived from all of them."""
    result = await db.execute(select(Claim).where(Claim.id == claim_id))
    claim = result.scalar_one_or_none()
    if claim is None:
        raise HTTPException(404, "Claim not found")
    reel_result = await db.execute(select(Reel).where(Reel.id == claim.reel_id))
    reel = reel_result.scalar_one()

    try:
        fact_check = await build_reel_fact_check(db, reel)
    except DuplicateFactCheckError as exc:
        await db.commit()  # persist the rejected/duplicate-flagged fact_check row
        raise HTTPException(409, f"DUPLICATE — DO NOT PUBLISH: {exc}") from exc
    except (ValueError, ProviderError) as exc:
        await db.rollback()
        raise HTTPException(400, str(exc)) from exc

    await db.commit()
    return await _load_fact_check_detail(db, fact_check.id)
