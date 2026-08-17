"""EXP-028 (research/RESEARCH_ROADMAP_V2.md Phase 7, direct re-run of
EXP-017 with its own named confound fixed): EXP-017
(compare_stance_taxonomies.py, research/EVIDENCE_STANCE_TAXONOMY_V2.md)
found 80% (16/20) of its comparison rows had an empty explanation on at
least one side -- because that script's new-taxonomy call never
replicated production evidence_analysis.py's substantiveness-retry
safety net (raw llama3.2 output, no Gemini quality-retry backstop).
Only 4 clean rows survived filtering, too few to say anything real
about whether the 8-category taxonomy reveals meaningful distinctions
the 4-category production scheme conflates.

This script is identical to compare_stance_taxonomies.py except the new
-taxonomy call now goes through the SAME substantiveness check + Gemini
quality-retry app/pipeline/evidence_analysis.py itself uses (mirrored,
not imported, since the production function is schema-bound to
EvidenceAnalysisItem, not the v2 8-category schema) -- a fair A/B
requires both sides to get the same real-world quality safety net, not
just the already-recorded original side.

Reuses the exact same real, already-persisted Evidence/Claim/Source
rows EXP-017 read (same query, same LIMIT/order, so the same 20 rows on
a stable table) -- this is a re-run of the same comparison with the
confound fixed, not a fresh sample.

Run: cd backend && ./.venv/bin/python research/evidence_reasoning_v2/compare_stance_taxonomies_v2.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.models import Claim, Evidence, EvidenceStance, Source  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.pipeline.evidence_analysis import _explanation_looks_substantive  # noqa: E402
from app.schemas.evidence_v2 import EvidenceAnalysisItemV2  # noqa: E402
from app.services.ai.factory import get_llm_provider  # noqa: E402
from app.services.ai.gemini_quota import GeminiUnavailableError, get_gemini_provider  # noqa: E402
from app.services.ai.prompts import wrap_untrusted  # noqa: E402
from app.services.storage.s3 import get_storage_client  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parents[3] / "research" / "results"

_PROMPT_VERSION_V2 = "evidence_analysis.v2-8category-candidate"
_SYSTEM_PROMPT_V2 = """You are the evidence-analysis stage of TruthLens. You will be given one \
claim and the full text of ONE retrieved, already-fetched source document. \
Classify this source's relationship to the claim using EXACTLY ONE of these \
8 categories:

- supports: the source directly confirms the claim's specific assertion.
- contradicts: the source directly refutes the claim's specific assertion.
- provides_context: relevant background that neither confirms nor denies \
the specific assertion.
- irrelevant: the source has no real connection to the claim's topic at all.
- same_event_wrong_entity: the source is about the same kind of event/topic \
but a DIFFERENT specific person/organization/place than the claim names.
- temporally_mismatched: the source is about the same topic/entities but a \
clearly different time period than the claim asserts.
- insufficient_detail: the source is genuinely on-topic (same event, same \
entities, right time) but too generic/vague to actually confirm or deny \
the claim's SPECIFIC assertion (e.g. a homepage, a department portal, a \
directory listing).
- mentions_only: the source mentions the claim's topic/entities in passing \
with no substantive content that bears on whether the claim is true.

Base your judgment ONLY on what is actually stated in the provided source \
text. Do not use outside knowledge. Quote or closely paraphrase the \
specific part of the source that justifies your choice in your explanation \
field."""

_TARGET_SAMPLE_SIZE = 20
_IRRELEVANT_WEIGHT = 15


async def main() -> None:
    settings = get_settings()
    provider = get_llm_provider()
    storage = get_storage_client()

    async with AsyncSessionLocal() as db:
        irrelevant_result = await db.execute(
            select(Evidence, Claim, Source)
            .join(Claim, Claim.id == Evidence.claim_id)
            .join(Source, Source.id == Evidence.source_id)
            .where(Evidence.stance == EvidenceStance.irrelevant)
            .limit(_IRRELEVANT_WEIGHT)
        )
        other_result = await db.execute(
            select(Evidence, Claim, Source)
            .join(Claim, Claim.id == Evidence.claim_id)
            .join(Source, Source.id == Evidence.source_id)
            .where(Evidence.stance != EvidenceStance.irrelevant)
            .limit(_TARGET_SAMPLE_SIZE - _IRRELEVANT_WEIGHT)
        )
        rows = irrelevant_result.all() + other_result.all()

        comparisons = []
        for evidence, claim, source in rows:
            full_text = storage.get_bytes(source.full_text_storage_key).decode("utf-8", errors="ignore")
            passage = full_text[:8000]
            user_content = (
                f"CLAIM: {claim.text}\n\n"
                f"SOURCE URL: {source.url}\n"
                f"SOURCE TITLE: {source.title or 'unknown'}\n"
                f"SOURCE TEXT:\n{wrap_untrusted(passage)}"
            )

            print(f"=== evidence {evidence.id} (original stance={evidence.stance.value}) ===", file=sys.stderr)
            retried_via_gemini = False
            try:
                result = await provider.structured_call(
                    model=settings.LLM_MODEL_EVIDENCE_ANALYSIS,
                    system_prompt=_SYSTEM_PROMPT_V2,
                    user_content=user_content,
                    output_schema=EvidenceAnalysisItemV2,
                    prompt_version=_PROMPT_VERSION_V2,
                )

                if (
                    settings.LLM_PROVIDER == "ollama"
                    and settings.GEMINI_API_KEY
                    and not _explanation_looks_substantive(result.parsed.explanation)
                ):
                    print("    explanation not substantive, retrying via Gemini...", file=sys.stderr)
                    try:
                        retry_result = await get_gemini_provider().structured_call(
                            model=settings.LLM_MODEL_GEMINI_FALLBACK,
                            system_prompt=_SYSTEM_PROMPT_V2,
                            user_content=user_content,
                            output_schema=EvidenceAnalysisItemV2,
                            prompt_version=_PROMPT_VERSION_V2,
                            db=db,
                            item_id=str(claim.id),
                            stage="evidence_analysis_v2_taxonomy_compare",
                        )
                    except GeminiUnavailableError as exc:
                        print(f"    Gemini retry unavailable: {exc}", file=sys.stderr)
                    else:
                        result = retry_result
                        retried_via_gemini = True

                new_stance = result.parsed.stance.value
                new_explanation = result.parsed.explanation
                print(f"    -> new stance: {new_stance} (retried={retried_via_gemini})", file=sys.stderr)
            except Exception as exc:  # noqa: BLE001
                new_stance = None
                new_explanation = f"ERROR: {exc}"
                print(f"    FAILED: {exc}", file=sys.stderr)

            comparisons.append({
                "evidence_id": str(evidence.id),
                "claim_text": claim.text,
                "source_url": source.url,
                "original_stance": evidence.stance.value,
                "original_explanation": evidence.explanation,
                "new_stance": new_stance,
                "new_explanation": new_explanation,
                "new_retried_via_gemini": retried_via_gemini,
                "changed_category": new_stance is not None and new_stance != evidence.stance.value,
            })

        await db.rollback()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "evidence_stance_taxonomy_comparison_v2_20260818.json"
    out_path.write_text(json.dumps(comparisons, indent=2, default=str))
    print(f"\nWrote {out_path}", file=sys.stderr)

    both_sides_substantive = [
        c for c in comparisons
        if c["original_explanation"] and c["original_explanation"].strip()
        and c["new_explanation"] and c["new_explanation"].strip() and not c["new_explanation"].startswith("ERROR:")
    ]
    n_changed = sum(1 for c in comparisons if c["changed_category"])
    n_irrelevant_reclassified = sum(
        1 for c in comparisons
        if c["original_stance"] == "irrelevant" and c["new_stance"] in
        ("same_event_wrong_entity", "temporally_mismatched", "insufficient_detail", "mentions_only")
    )
    n_irrelevant_total = sum(1 for c in comparisons if c["original_stance"] == "irrelevant")
    n_retried = sum(1 for c in comparisons if c["new_retried_via_gemini"])
    print(f"\nTotal compared: {len(comparisons)}", file=sys.stderr)
    print(f"Retried via Gemini: {n_retried}", file=sys.stderr)
    print(f"Clean rows (both sides substantive): {len(both_sides_substantive)}/{len(comparisons)}", file=sys.stderr)
    print(f"Category changed at all: {n_changed}", file=sys.stderr)
    print(
        f"Originally 'irrelevant' reclassified into one of the 4 new categories: "
        f"{n_irrelevant_reclassified}/{n_irrelevant_total}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    asyncio.run(main())
