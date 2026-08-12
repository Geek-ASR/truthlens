"""Stage 6b/7: propose a verdict from the evidence matrix, then run it
through deterministic anti-hallucination validation before persisting
(product spec §16 Model 5 + §17)."""
import re
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import (
    ActorType,
    Claim,
    ClaimStatus,
    ConfidenceBand,
    Evidence,
    Source,
    ValidationStatus,
    Verdict,
    VerdictLabel,
)
from app.pipeline.audit import record_audit
from app.pipeline.validation import validate_verdict
from app.schemas.verdict import VerdictProposal
from app.services.ai.base import LLMCallResult
from app.services.ai.factory import get_llm_provider
from app.services.ai.prompts import VERDICT_PROMPT_VERSION, VERDICT_SYSTEM_PROMPT

logger = get_logger(__name__)

# Same "schema-valid but substantively empty" failure already found and
# fixed in claim_extraction.py and content_generation.py
# (docs/CURRENT_ARCHITECTURE.md), found here too via live testing: a real
# verdict's reasoning_summary was made ENTIRELY of
# "[[evidence_id=... | source=...]]" citation markup — no actual prose —
# which passed schema validation (it's a non-empty string) but explains
# nothing to a reader. Checked after stripping that markup, not before,
# so a reasoning_summary that's real prose PLUS an inline citation still
# passes normally.
_INTERNAL_MARKUP_PATTERN = re.compile(r"\[\[.*?\]\]", re.DOTALL)
_MIN_REASONING_WORDS = 6


def _reasoning_looks_substantive(text: str) -> bool:
    stripped = _INTERNAL_MARKUP_PATTERN.sub("", text)
    words = re.findall(r"[A-Za-z]{2,}", stripped)
    return len(words) >= _MIN_REASONING_WORDS


def confidence_to_band(confidence: float) -> ConfidenceBand:
    if confidence >= 0.90:
        return ConfidenceBand.very_high
    if confidence >= 0.75:
        return ConfidenceBand.high
    if confidence >= 0.60:
        return ConfidenceBand.moderate
    return ConfidenceBand.requires_review


def _build_evidence_matrix_text(evidence_rows: list[Evidence], sources_by_id: dict) -> str:
    lines = []
    for e in evidence_rows:
        source = sources_by_id[e.source_id]
        lines.append(
            f"- evidence_id={e.id} | source_id={e.source_id} | stance={e.stance.value} | "
            f"directness={e.directness.value} | source_type={source.source_type.value} | "
            f"reliability={source.reliability_score} | publisher={source.publisher or source.url} | "
            f"explanation: {e.explanation}"
        )
    return "\n".join(lines)


async def propose_verdict(
    db: AsyncSession, claim: Claim, evidence_rows: list[Evidence], sources: list[Source]
) -> Verdict:
    settings = get_settings()
    sources_by_id = {s.id: s for s in sources}

    if not evidence_rows:
        # No evidence retrieved at all — UNVERIFIED without calling the LLM,
        # since there is nothing for it to reason about.
        return await _persist_unverified(
            db, claim, reason="No evidence sources were retrieved for this claim.", model="n/a"
        )

    evidence_matrix_text = _build_evidence_matrix_text(evidence_rows, sources_by_id)
    user_content = f"CLAIM: {claim.text}\n\nEVIDENCE MATRIX:\n{evidence_matrix_text}"

    provider = get_llm_provider()
    result = await provider.structured_call(
        model=settings.LLM_MODEL_VERDICT,
        system_prompt=VERDICT_SYSTEM_PROMPT,
        user_content=user_content,
        output_schema=VerdictProposal,
        prompt_version=VERDICT_PROMPT_VERSION,
    )

    if (
        settings.LLM_PROVIDER == "ollama"
        and settings.GEMINI_API_KEY
        and not _reasoning_looks_substantive(result.parsed.reasoning_summary)
    ):
        logger.warning(
            "verdict_reasoning_not_substantive_retrying_via_gemini",
            claim_id=str(claim.id),
            model=result.model,
        )
        from app.services.ai.gemini_provider import GeminiProvider

        retry_result: LLMCallResult = await GeminiProvider().structured_call(
            model=settings.LLM_MODEL_GEMINI_FALLBACK,
            system_prompt=VERDICT_SYSTEM_PROMPT,
            user_content=user_content,
            output_schema=VerdictProposal,
            prompt_version=VERDICT_PROMPT_VERSION,
        )
        await record_audit(
            db,
            entity_type="claim",
            entity_id=claim.id,
            actor_type=ActorType.system,
            actor="verdict_stage",
            action="verdict_reasoning_quality_retry",
            input_summary={"original_model": result.model},
            output_summary={"retry_model": retry_result.model},
        )
        result = retry_result

    evidence_by_id = {e.id: e for e in evidence_rows}
    source_by_evidence_id = {e.id: sources_by_id[e.source_id] for e in evidence_rows}
    outcome = validate_verdict(result.parsed, evidence_by_id, source_by_evidence_id)

    now = datetime.now(timezone.utc)
    verdict = Verdict(
        claim_id=claim.id,
        verdict=outcome.verdict,
        confidence=outcome.confidence,
        confidence_band=confidence_to_band(outcome.confidence),
        reasoning_summary=result.parsed.reasoning_summary
        if outcome.status.value == "passed"
        else f"{result.parsed.reasoning_summary}\n\n[VALIDATION NOTE: {'; '.join(outcome.notes)}]",
        cited_evidence_ids=result.parsed.cited_evidence_ids if outcome.status.value == "passed" else [],
        validation_status=outcome.status,
        verdict_model=f"{result.model}:{result.prompt_version}",
        is_current=True,
        created_at=now,
    )
    db.add(verdict)
    claim.status = ClaimStatus.researched
    await db.flush()

    await record_audit(
        db,
        entity_type="claim",
        entity_id=claim.id,
        actor_type=ActorType.ai_stage,
        actor=f"llm:{result.model}",
        action="verdict",
        input_summary={"evidence_count": len(evidence_rows)},
        output_summary={
            "proposed_verdict": result.parsed.verdict.value,
            "final_verdict": outcome.verdict.value,
            "validation_status": outcome.status.value,
        },
        prompt_version=result.prompt_version,
        tokens=result.token_usage_dict(),
    )
    return verdict


async def _persist_unverified(db: AsyncSession, claim: Claim, *, reason: str, model: str) -> Verdict:
    now = datetime.now(timezone.utc)
    verdict = Verdict(
        claim_id=claim.id,
        verdict=VerdictLabel.UNVERIFIED,
        confidence=0.0,
        confidence_band=ConfidenceBand.requires_review,
        reasoning_summary=reason,
        cited_evidence_ids=[],
        validation_status=ValidationStatus.passed,
        verdict_model=model,
        is_current=True,
        created_at=now,
    )
    db.add(verdict)
    claim.status = ClaimStatus.researched
    await db.flush()
    await record_audit(
        db,
        entity_type="claim",
        entity_id=claim.id,
        actor_type=ActorType.system,
        actor="verdict_stage",
        action="verdict_unverified_no_evidence",
        output_summary={"reason": reason},
    )
    return verdict
