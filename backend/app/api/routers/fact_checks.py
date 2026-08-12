from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, RequireAdmin, RequireReviewer
from app.core.exceptions import ProviderError
from app.db.models import (
    ActorType,
    Claim,
    Correction,
    Evidence,
    FactCheck,
    FactCheckStatus,
    GeneratedPost,
    InstagramAccount,
    Reel,
    Slide,
    Source,
    Verdict,
)
from app.pipeline import content_generation, slide_generation
from app.pipeline.audit import record_audit
from app.services.storage.s3 import get_storage_client
from app.schemas.common import FactCheckStatus as FactCheckStatusSchema
from app.schemas.fact_check import (
    CorrectionCreate,
    FactCheckApproveRequest,
    FactCheckDetail,
    FactCheckEditRequest,
    FactCheckRejectRequest,
    FactCheckSummary,
    SlideOut,
)

router = APIRouter()


async def _load_fact_check_detail(db: AsyncSession, fact_check_id) -> FactCheckDetail:
    result = await db.execute(select(FactCheck).where(FactCheck.id == fact_check_id))
    fact_check = result.scalar_one_or_none()
    if fact_check is None:
        raise HTTPException(404, "Fact check not found")

    reel = (await db.execute(select(Reel).where(Reel.id == fact_check.reel_id))).scalar_one()
    primary_claim = (
        await db.execute(select(Claim).where(Claim.id == fact_check.primary_claim_id))
    ).scalar_one()
    covered_claims = []
    if fact_check.covered_claim_ids:
        covered_claims = list(
            (await db.execute(select(Claim).where(Claim.id.in_(fact_check.covered_claim_ids)))).scalars()
        )

    # Evidence for every claim this fact-check covers, not just the
    # primary one — a reel-level fact-check can rest on several claims'
    # worth of evidence (app/pipeline/orchestrator.build_reel_fact_check).
    evidence_claim_ids = {c.id for c in covered_claims} | {primary_claim.id}
    evidence_rows = list(
        (
            await db.execute(
                select(Evidence)
                .options(selectinload(Evidence.source))
                .where(Evidence.claim_id.in_(evidence_claim_ids))
            )
        ).scalars()
    )

    current_verdict = None
    if fact_check.current_verdict_id:
        current_verdict = (
            await db.execute(select(Verdict).where(Verdict.id == fact_check.current_verdict_id))
        ).scalar_one_or_none()

    slides = list(
        (
            await db.execute(select(Slide).where(Slide.fact_check_id == fact_check.id).order_by(Slide.position))
        ).scalars()
    )
    storage = get_storage_client()
    slide_out = [
        SlideOut(
            id=s.id,
            position=s.position,
            slide_type=s.slide_type,
            image_url=storage.public_url(s.image_storage_key),
            template_version=s.template_version,
            content_json=s.content_json,
        )
        for s in slides
    ]

    return FactCheckDetail(
        id=fact_check.id,
        status=fact_check.status,
        reel=reel,
        primary_claim=primary_claim,
        covered_claims=covered_claims,
        evidence=evidence_rows,
        current_verdict=current_verdict,
        caption_text=fact_check.caption_text,
        methodology_note=fact_check.methodology_note,
        slides=slide_out,
        review_notes=fact_check.review_notes,
        duplicate_of_fact_check_id=fact_check.duplicate_of_fact_check_id,
    )


@router.get("", response_model=list[FactCheckSummary])
async def list_fact_checks(
    db: DbSession, current_user: RequireReviewer, status: FactCheckStatusSchema | None = None, limit: int = 50
):
    query = select(FactCheck, Claim, Verdict).join(Claim, FactCheck.primary_claim_id == Claim.id).outerjoin(
        Verdict, FactCheck.current_verdict_id == Verdict.id
    )
    if status is not None:
        query = query.where(FactCheck.status == status)
    query = query.order_by(FactCheck.created_at.desc()).limit(limit)

    rows = (await db.execute(query)).all()
    return [
        FactCheckSummary(
            id=fc.id,
            status=fc.status,
            reel_id=fc.reel_id,
            primary_claim_text=claim.text,
            verdict=v.verdict.value if v else None,
            confidence=v.confidence if v else None,
            created_at=fc.created_at,
        )
        for fc, claim, v in rows
    ]


@router.get("/{fact_check_id}", response_model=FactCheckDetail)
async def get_fact_check(fact_check_id: str, db: DbSession, current_user: RequireReviewer):
    return await _load_fact_check_detail(db, fact_check_id)


@router.patch("/{fact_check_id}", response_model=FactCheckDetail)
async def edit_fact_check(
    fact_check_id: str, payload: FactCheckEditRequest, db: DbSession, current_user: RequireReviewer
):
    result = await db.execute(select(FactCheck).where(FactCheck.id == fact_check_id))
    fact_check = result.scalar_one_or_none()
    if fact_check is None:
        raise HTTPException(404, "Fact check not found")
    if fact_check.status == FactCheckStatus.published:
        raise HTTPException(400, "Cannot edit a published fact_check directly — use the corrections endpoint.")

    before = {"caption_text": fact_check.caption_text, "review_notes": fact_check.review_notes}
    if payload.caption_text is not None:
        fact_check.caption_text = payload.caption_text
    if payload.review_notes is not None:
        fact_check.review_notes = payload.review_notes
    await db.flush()

    await record_audit(
        db,
        entity_type="fact_check",
        entity_id=fact_check.id,
        actor_type=ActorType.human,
        actor=current_user.email,
        action="edit",
        input_summary=before,
        output_summary={"caption_text": fact_check.caption_text, "review_notes": fact_check.review_notes},
    )
    await db.commit()
    return await _load_fact_check_detail(db, fact_check.id)


@router.post("/{fact_check_id}/approve", response_model=FactCheckDetail)
async def approve_fact_check(
    fact_check_id: str, payload: FactCheckApproveRequest, db: DbSession, current_user: RequireReviewer
):
    """Human Approval Mode gate (product spec §20, default ON). Creates
    the GeneratedPost — actual publishing happens via
    POST /api/publishing/{fact_check_id}/publish, so a failed Graph API
    call never silently re-triggers a duplicate approval."""
    result = await db.execute(select(FactCheck).where(FactCheck.id == fact_check_id))
    fact_check = result.scalar_one_or_none()
    if fact_check is None:
        raise HTTPException(404, "Fact check not found")
    if fact_check.status != FactCheckStatus.ready_for_review:
        raise HTTPException(400, f"Cannot approve a fact_check in status {fact_check.status.value}")

    account = (
        await db.execute(select(InstagramAccount).where(InstagramAccount.id == payload.instagram_account_id))
    ).scalar_one_or_none()
    if account is None:
        raise HTTPException(404, "Instagram account not found")

    slide_ids = list(
        (await db.execute(select(Slide.id).where(Slide.fact_check_id == fact_check.id))).scalars()
    )
    from app.pipeline.publishing import build_idempotency_key

    idempotency_key = build_idempotency_key(fact_check.id, slide_ids)

    existing = (
        await db.execute(select(GeneratedPost).where(GeneratedPost.fact_check_id == fact_check.id))
    ).scalar_one_or_none()
    if existing is None:
        generated_post = GeneratedPost(
            fact_check_id=fact_check.id,
            instagram_account_id=account.id,
            idempotency_key=idempotency_key,
            approved_by_user_id=current_user.id,
            approved_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(generated_post)

    fact_check.status = FactCheckStatus.approved
    fact_check.reviewed_by_user_id = current_user.id
    fact_check.reviewed_at = datetime.now(timezone.utc)
    if payload.review_notes:
        fact_check.review_notes = payload.review_notes
    await db.flush()

    await record_audit(
        db,
        entity_type="fact_check",
        entity_id=fact_check.id,
        actor_type=ActorType.human,
        actor=current_user.email,
        action="approve",
        output_summary={"instagram_account_id": str(account.id)},
    )
    await db.commit()
    return await _load_fact_check_detail(db, fact_check.id)


@router.post("/{fact_check_id}/reject", response_model=FactCheckDetail)
async def reject_fact_check(
    fact_check_id: str, payload: FactCheckRejectRequest, db: DbSession, current_user: RequireReviewer
):
    result = await db.execute(select(FactCheck).where(FactCheck.id == fact_check_id))
    fact_check = result.scalar_one_or_none()
    if fact_check is None:
        raise HTTPException(404, "Fact check not found")

    fact_check.status = FactCheckStatus.rejected
    fact_check.reviewed_by_user_id = current_user.id
    fact_check.reviewed_at = datetime.now(timezone.utc)
    fact_check.review_notes = payload.review_notes
    await db.flush()

    await record_audit(
        db,
        entity_type="fact_check",
        entity_id=fact_check.id,
        actor_type=ActorType.human,
        actor=current_user.email,
        action="reject",
        output_summary={"review_notes": payload.review_notes},
    )
    await db.commit()
    return await _load_fact_check_detail(db, fact_check.id)


@router.post("/{fact_check_id}/corrections", response_model=FactCheckDetail)
async def create_correction(
    fact_check_id: str, payload: CorrectionCreate, db: DbSession, current_user: RequireAdmin
):
    """product spec §26: corrections never silently rewrite history. Call
    POST /api/claims/{claim_id}/research-again first to produce a new
    current verdict for the primary claim, then call this endpoint to
    record the correction and regenerate the carousel from it."""
    result = await db.execute(select(FactCheck).where(FactCheck.id == fact_check_id))
    fact_check = result.scalar_one_or_none()
    if fact_check is None:
        raise HTTPException(404, "Fact check not found")
    if fact_check.status != FactCheckStatus.published:
        raise HTTPException(400, "Corrections apply only to already-published fact_checks.")

    claim = (await db.execute(select(Claim).where(Claim.id == fact_check.primary_claim_id))).scalar_one()
    new_verdict = (
        await db.execute(
            select(Verdict)
            .where(Verdict.claim_id == claim.id, Verdict.is_current.is_(True))
            .order_by(Verdict.created_at.desc())
        )
    ).scalars().first()
    if new_verdict is None or new_verdict.id == fact_check.current_verdict_id:
        raise HTTPException(
            400, "No new current verdict found. Run research-again on the primary claim before correcting."
        )

    previous_verdict_id = fact_check.current_verdict_id

    correction = Correction(
        fact_check_id=fact_check.id,
        previous_verdict_id=previous_verdict_id,
        new_verdict_id=new_verdict.id,
        correction_reason=payload.correction_reason,
        new_evidence_source_ids=payload.new_evidence_source_ids,
        corrected_by_user_id=current_user.id,
        published_correction_note=payload.published_correction_note,
        created_at=datetime.now(timezone.utc),
    )
    db.add(correction)

    reel = (await db.execute(select(Reel).where(Reel.id == fact_check.reel_id))).scalar_one()
    evidence_rows = list(
        (await db.execute(select(Evidence).where(Evidence.claim_id == claim.id))).scalars()
    )
    source_ids = [e.source_id for e in evidence_rows]
    sources = (
        list((await db.execute(select(Source).where(Source.id.in_(source_ids)))).scalars())
        if source_ids
        else []
    )

    try:
        generated, caption, caption_sources = await content_generation.generate_content(
            db, claim=claim, verdict=new_verdict, reel=reel, evidence_rows=evidence_rows, sources=sources
        )
        await slide_generation.generate_slides(
            db,
            fact_check=fact_check,
            claim=claim,
            verdict=new_verdict,
            reel=reel,
            generated=generated,
            caption_sources=caption_sources,
        )
    except ProviderError as exc:
        await db.rollback()
        raise HTTPException(502, f"Correction content regeneration failed: {exc}") from exc

    fact_check.current_verdict_id = new_verdict.id
    fact_check.caption_text = (
        f"⚠️ CORRECTION\n{payload.published_correction_note}\n\n{'-'*20}\n\n{caption}"
    )
    fact_check.status = FactCheckStatus.corrected
    await db.flush()

    await record_audit(
        db,
        entity_type="fact_check",
        entity_id=fact_check.id,
        actor_type=ActorType.human,
        actor=current_user.email,
        action="correction",
        output_summary={
            "previous_verdict_id": str(previous_verdict_id),
            "new_verdict_id": str(new_verdict.id),
        },
    )
    await db.commit()
    return await _load_fact_check_detail(db, fact_check.id)
