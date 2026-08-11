"""Stage 6: for each retrieved source, determine its stance toward the
claim, reading ONLY that source's archived text (product spec §16 Model
4). After all sources for a claim are analyzed, corroboration and
directness on each source's reliability_breakdown are refined from the
actual evidence rows (source_scoring.update_after_evidence)."""
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import ActorType, Claim, Evidence, Source
from app.pipeline.audit import record_audit
from app.pipeline.source_scoring import update_after_evidence
from app.schemas.evidence import EvidenceAnalysisItem
from app.services.ai.anthropic_provider import get_llm_provider
from app.services.ai.prompts import (
    EVIDENCE_ANALYSIS_PROMPT_VERSION,
    EVIDENCE_ANALYSIS_SYSTEM_PROMPT,
    wrap_untrusted,
)
from app.services.storage.s3 import get_storage_client

_MAX_PASSAGE_CHARS = 8000


async def analyze_evidence(db: AsyncSession, claim: Claim, sources: list[Source]) -> list[Evidence]:
    settings = get_settings()
    storage = get_storage_client()
    provider = get_llm_provider()

    evidence_rows: list[Evidence] = []
    now = datetime.now(timezone.utc)
    total_tokens = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }

    for source in sources:
        full_text = storage.get_bytes(source.full_text_storage_key).decode("utf-8", errors="ignore")
        passage = full_text[:_MAX_PASSAGE_CHARS]

        user_content = (
            f"CLAIM: {claim.text}\n\n"
            f"SOURCE URL: {source.url}\n"
            f"SOURCE TITLE: {source.title or 'unknown'}\n"
            f"SOURCE TEXT:\n{wrap_untrusted(passage)}"
        )

        result = await provider.structured_call(
            model=settings.LLM_MODEL_EVIDENCE_ANALYSIS,
            system_prompt=EVIDENCE_ANALYSIS_SYSTEM_PROMPT,
            user_content=user_content,
            output_schema=EvidenceAnalysisItem,
            prompt_version=EVIDENCE_ANALYSIS_PROMPT_VERSION,
        )

        for key, value in result.token_usage_dict().items():
            total_tokens[key] += value

        analysis = result.parsed
        evidence = Evidence(
            claim_id=claim.id,
            source_id=source.id,
            stance=analysis.stance,
            explanation=analysis.explanation,
            directness=analysis.directness,
            analysis_model=f"{result.model}:{result.prompt_version}",
            created_at=now,
        )
        db.add(evidence)
        evidence_rows.append(evidence)

        # relevant_passage is refined to the excerpt actually cited, when the
        # model's explanation quotes/paraphrases a shorter section than the
        # coarse fetch-time excerpt.
        source.relevant_passage = passage[:2000]

    await db.flush()

    # Refine corroboration + directness per source now that all stances for
    # this claim are known (docs/FACT_CHECK_METHODOLOGY.md §3). Numerator
    # and denominator are both counted over the same population (every
    # other source with evidence for this claim) so the ratio never
    # exceeds 1.0.
    stances_by_source = {e.source_id: e.stance.value for e in evidence_rows}
    other_sources_count = max(len(sources) - 1, 0)
    agreeing_counts: dict = {}
    for src in sources:
        this_stance = stances_by_source.get(src.id)
        if this_stance in ("supports", "contradicts"):
            agreeing_counts[src.id] = sum(
                1
                for other in sources
                if other.id != src.id and stances_by_source.get(other.id) == this_stance
            )
        else:
            agreeing_counts[src.id] = 0

    for evidence in evidence_rows:
        source = next(s for s in sources if s.id == evidence.source_id)
        new_score, new_breakdown = update_after_evidence(
            source.reliability_breakdown,
            directness=evidence.directness.value,
            agreeing_count=agreeing_counts[source.id],
            total_independent_count=other_sources_count,
        )
        source.reliability_score = new_score
        source.reliability_breakdown = new_breakdown

    await db.flush()

    await record_audit(
        db,
        entity_type="claim",
        entity_id=claim.id,
        actor_type=ActorType.ai_stage,
        actor=f"llm:{settings.LLM_MODEL_EVIDENCE_ANALYSIS}",
        action="evidence_analysis",
        input_summary={"source_count": len(sources)},
        output_summary={
            "stances": {str(e.source_id): e.stance.value for e in evidence_rows}
        },
        prompt_version=EVIDENCE_ANALYSIS_PROMPT_VERSION,
        tokens=total_tokens,
    )
    return evidence_rows
