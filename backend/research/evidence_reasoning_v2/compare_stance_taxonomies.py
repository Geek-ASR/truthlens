"""EXP-017 (research/RESEARCH_ROADMAP_V2.md Phase 7): does the 8
-category evidence-stance taxonomy (app/schemas/evidence_v2.py) reveal
real, meaningful distinctions the current 4-category scheme
(app/schemas/evidence.py, production) conflates -- specifically, does it
separate the "genuinely irrelevant" cases from the "on-topic but too
generic/wrong-entity/wrong-time" cases the 4-category scheme has nowhere
to put but `irrelevant`?

Reuses REAL, already-persisted Evidence rows (no new fetching, no new
search calls) -- 207 real rows already exist in the dev DB from earlier
pipeline runs this session. For a real sample (weighted toward
`irrelevant`, the dominant and most interesting-to-decompose category),
runs the NEW 8-category candidate prompt against the exact same
claim+source pair the ORIGINAL 4-category stance is already recorded
for, and compares. The original stance is read directly from the DB,
not re-run -- this halves the real LLM-call cost of the comparison and
guarantees the two are compared on identical input.

No production code touched -- app/pipeline/evidence_analysis.py and its
4-category schema are completely unchanged by this script.

Run: cd backend && ./.venv/bin/python research/evidence_reasoning_v2/compare_stance_taxonomies.py
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
from app.schemas.evidence_v2 import EvidenceAnalysisItemV2  # noqa: E402
from app.services.ai.factory import get_llm_provider  # noqa: E402
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
_IRRELEVANT_WEIGHT = 15  # of the 20, prioritize irrelevant-labeled rows -- the dominant, most interesting-to-decompose category


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
            # Same construction as production evidence_analysis.py (same
            # truncation length, same field layout) so this is a fair,
            # faithful A/B on identical input, not a differently-shaped prompt.
            full_text = storage.get_bytes(source.full_text_storage_key).decode("utf-8", errors="ignore")
            passage = full_text[:8000]
            user_content = (
                f"CLAIM: {claim.text}\n\n"
                f"SOURCE URL: {source.url}\n"
                f"SOURCE TITLE: {source.title or 'unknown'}\n"
                f"SOURCE TEXT:\n{wrap_untrusted(passage)}"
            )

            print(f"=== evidence {evidence.id} (original stance={evidence.stance.value}) ===", file=sys.stderr)
            try:
                result = await provider.structured_call(
                    model=settings.LLM_MODEL_EVIDENCE_ANALYSIS,
                    system_prompt=_SYSTEM_PROMPT_V2,
                    user_content=user_content,
                    output_schema=EvidenceAnalysisItemV2,
                    prompt_version=_PROMPT_VERSION_V2,
                )
                new_stance = result.parsed.stance.value
                new_explanation = result.parsed.explanation
                print(f"    -> new stance: {new_stance}", file=sys.stderr)
            except Exception as exc:  # noqa: BLE001 -- a real failure is a real, reportable outcome
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
                "changed_category": new_stance is not None and new_stance != evidence.stance.value,
            })

        await db.rollback()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "evidence_stance_taxonomy_comparison_20260818.json"
    out_path.write_text(json.dumps(comparisons, indent=2, default=str))
    print(f"\nWrote {out_path}", file=sys.stderr)

    n_changed = sum(1 for c in comparisons if c["changed_category"])
    n_irrelevant_reclassified = sum(
        1 for c in comparisons
        if c["original_stance"] == "irrelevant" and c["new_stance"] in
        ("same_event_wrong_entity", "temporally_mismatched", "insufficient_detail", "mentions_only")
    )
    n_irrelevant_total = sum(1 for c in comparisons if c["original_stance"] == "irrelevant")
    print(f"\nTotal compared: {len(comparisons)}", file=sys.stderr)
    print(f"Category changed at all: {n_changed}", file=sys.stderr)
    print(
        f"Originally 'irrelevant' reclassified into one of the 4 new categories: "
        f"{n_irrelevant_reclassified}/{n_irrelevant_total}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    asyncio.run(main())
