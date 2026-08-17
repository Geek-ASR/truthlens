"""research/RESEARCH_ROADMAP_V2.md Phase 4: entity-consistency check v2.

STATUS: integrated into production as of this same pass -- see
app/pipeline/validation.py's Check 7 (ValidationStatus.
downgraded_entity_mismatch). This script now re-derives the exact same
logic that check uses (imported directly, not copied, so there is no
drift between what's evaluated here and what runs in production) purely
for standalone corpus-level reporting (violation/exact-match/fuzzy-match
counts across many evidence rows at once, which validate_verdict()'s
per-verdict, early-return design doesn't surface on its own).

Extends the v1 prototype (research/entity_consistency_eval.py,
ENTITY_CONSISTENCY_EVALUATION.md, this project's own prior audit) with
the 3 concrete fixes that audit itself named as required before another
evaluation pass would mean anything:

1. Filter claim entities to PERSON/ORGANIZATION/LOCATION before
   evaluating -- v1's 4 false positives were ALL the abstract-concept
   entity {"name": "Democracy", "type": "concept"} matched against real
   constitutional-law text, not a meaningful entity-consistency test.
   Real observed Claim.entities `type` values are messy free text
   ("person", "Organization", "EducationalInstitution", "Examination",
   "concept", ...) -- _normalize_entity_type() canonicalizes what
   claim_extraction ACTUALLY produces today into a fixed vocabulary.
   This is NOT the roadmap's full aspirational 7-category schema
   (PERSON/ORGANIZATION/LOCATION/EVENT/DATE/NUMBER/POLITICAL_ACTOR) --
   EVENT/DATE/NUMBER/POLITICAL_ACTOR would require a claim_extraction
   prompt/schema change this pass does not make, disclosed here rather
   than silently narrowed.

2. Real data pulled directly from the live DB (DEV split only -- Phase
   4's own dataset instruction), not a throwaway /tmp intermediate file
   -- reproducible and permanent this time.

3. A disclosed, SEPARATE fuzzy-match signal (difflib.SequenceMatcher,
   same tool this session's claim-deduplication work already used) for
   the real transliteration-variance gap v1 found (Dipke/Deepke).
   Calibrated against this project's own real cases, not guessed:
   "abhijit dipke" vs "abhijeet deepke" (the real case that SHOULD
   match) scores 0.786; "delhi police" vs "burdwan police" and "karni
   sena" vs "sri ram sena" (the real cases that must NOT collapse into
   each other -- exactly Step 9's "Delhi Police vs Burdwan Police" test
   class) score 0.615 and 0.545. Threshold set to 0.75: clears the real
   positive with margin, rejects both real negatives with much larger
   margin. Reported as its own column (fuzzy_matched_entities),
   separate from the exact-match result, never silently merged into one
   number.

Run: cd backend && ./.venv/bin/python -m research.entity_consistency_v2.evaluate
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from sqlalchemy import select  # noqa: E402

from app.db.models import BenchmarkSplit, Claim, DatasetType, Evidence, EvidenceStance, Reel, Source  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.pipeline.validation import (  # noqa: E402
    _ENTITY_EVALUABLE_TYPES as _EVALUABLE_TYPES,
    _entity_exact_match as _exact_match,
    _entity_fuzzy_match as _fuzzy_match,
    _normalize_entity_type,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RESULTS_PATH = _REPO_ROOT / "research" / "results" / "entity_consistency_eval_v2_20260818.json"


def check_entity_consistency(claim_entities: list[dict], evidence_title: str, evidence_passage: str) -> dict:
    """Re-derives the same per-row detail app.pipeline.validation's Check
    7 computes internally (via the same imported primitives above, not a
    reimplementation) but keeps the richer exact-vs-fuzzy breakdown that
    script's corpus-level reporting needs and Check 7's single pass/fail
    boolean doesn't expose."""
    typed_entities = [
        {**e, "normalized_type": _normalize_entity_type(e.get("type"))}
        for e in (claim_entities or [])
    ]
    evaluable_entities = [e for e in typed_entities if e["normalized_type"] in _EVALUABLE_TYPES]
    excluded_entities = [e for e in typed_entities if e["normalized_type"] not in _EVALUABLE_TYPES]

    if not evaluable_entities:
        return {
            "evaluable": False,
            "excluded_entities": [e["name"] for e in excluded_entities],
        }

    combined = f"{evidence_title or ''} {evidence_passage or ''}"
    text_l = combined.lower()
    exact_matched = [e["name"] for e in evaluable_entities if _exact_match(e["name"], text_l)]
    fuzzy_only_matched = [
        e["name"] for e in evaluable_entities
        if e["name"] not in exact_matched and _fuzzy_match(e["name"], text_l)
    ]
    return {
        "evaluable": True,
        "has_match": bool(exact_matched or fuzzy_only_matched),
        "exact_matched_entities": exact_matched,
        "fuzzy_matched_entities": fuzzy_only_matched,
        "claim_entities_checked": [e["name"] for e in evaluable_entities],
        "excluded_entities": [e["name"] for e in excluded_entities],
    }


async def _load_real_data() -> dict:
    data = {}
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Claim)
            .join(Reel, Reel.id == Claim.reel_id)
            .where(Reel.dataset_type == DatasetType.benchmark, Reel.benchmark_split == BenchmarkSplit.dev)
        )
        claims = result.scalars().unique().all()
        for claim in claims:
            ev_result = await db.execute(
                select(Evidence, Source)
                .join(Source, Source.id == Evidence.source_id)
                .where(Evidence.claim_id == claim.id)
            )
            rows = ev_result.all()
            if not rows:
                continue
            data[str(claim.id)] = {
                "text": claim.text,
                "entities": claim.entities or [],
                "evidence": [
                    {
                        "id": str(ev.id),
                        "stance": ev.stance.value,
                        "title": src.title,
                        "passage": src.relevant_passage,
                    }
                    for ev, src in rows
                ],
            }
    return data


async def main() -> None:
    data = await _load_real_data()
    results = []
    for claim_id, d in data.items():
        for ev in d["evidence"]:
            if ev["stance"] == EvidenceStance.irrelevant.value:
                continue
            check = check_entity_consistency(d["entities"], ev["title"], ev["passage"])
            results.append({
                "claim_id": claim_id,
                "claim_text": d["text"],
                "evidence_id": ev["id"],
                "evidence_title": ev["title"],
                "stance": ev["stance"],
                **check,
            })

    print(f"Total non-irrelevant evidence rows evaluated: {len(results)}")
    evaluable = [r for r in results if r["evaluable"]]
    not_evaluable = [r for r in results if not r["evaluable"]]
    print(f"Evaluable (claim had >=1 PERSON/ORGANIZATION/LOCATION entity): {len(evaluable)}")
    print(f"NOT evaluable (claim had zero evaluable-type entities): {len(not_evaluable)}")
    violations = [r for r in evaluable if not r["has_match"]]
    exact_only = [r for r in evaluable if r["has_match"] and r["exact_matched_entities"]]
    fuzzy_only = [r for r in evaluable if r["has_match"] and not r["exact_matched_entities"] and r["fuzzy_matched_entities"]]
    print(f"Violations (no exact or fuzzy match): {len(violations)}")
    print(f"Matched via exact substring: {len(exact_only)}")
    print(f"Matched via fuzzy match ONLY (transliteration-variance recovery): {len(fuzzy_only)}")
    print()
    for r in results:
        if not r["evaluable"]:
            flag = "SKIP(no evaluable entities)"
        elif not r["has_match"]:
            flag = "VIOLATION"
        elif r["fuzzy_matched_entities"] and not r["exact_matched_entities"]:
            flag = "ok(fuzzy)"
        else:
            flag = "ok(exact)"
        print(f"[{flag:28s}] {r['claim_text'][:45]:45s} <- [{r['stance']:11s}] {r['evidence_title']}")

    _RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _RESULTS_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {_RESULTS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
