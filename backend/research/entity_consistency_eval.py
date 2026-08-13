"""Phase 5: entity-consistency validator, prototyped and evaluated
INDEPENDENTLY against real data -- not assumed to help, not wired into
the production validator (backend/app/pipeline/validation.py) until this
evaluation gives a real reason to.

Design: for each cited evidence row where evidence_analysis assigned a
non-irrelevant stance (supports/contradicts -- i.e., stances that
actually influence a verdict), check whether at least one of the claim's
own extracted named entities (Claim.entities, already populated by
claim_extraction, real production data) appears in that evidence's own
title+passage text. A claim with zero extracted entities cannot be
evaluated by this check at all -- flagged as such, not silently skipped
as a pass.

A small, explicit, disclosed alias table handles the exact case Phase 5's
own brief names (government-institution synonyms); no fuzzy/ML aliasing,
consistent with every other deterministic check in this project.

Run: cd backend && .venv/bin/python research/entity_consistency_eval.py
Reads /tmp/entity_check_data.json (real claim+evidence data pulled live
from the DB for the same 9 real cases research/VALIDATOR_EVALUATION.md
already audits -- see that file for how this data was pulled).
"""
import json
from pathlib import Path

_ALIAS_GROUPS = [
    {"government of india", "union government", "centre", "central government", "govt of india"},
]


def _normalize(name: str) -> str:
    return name.lower().strip()


def _entity_in_text(entity_name: str, text: str) -> bool:
    name = _normalize(entity_name)
    text_l = (text or "").lower()
    if name and name in text_l:
        return True
    for group in _ALIAS_GROUPS:
        if name in group:
            return any(alias in text_l for alias in group)
    return False


def check_entity_consistency(claim_entities: list[dict], evidence_title: str, evidence_passage: str) -> dict:
    if not claim_entities:
        return {"evaluable": False}
    combined = f"{evidence_title or ''} {evidence_passage or ''}"
    matched = [e["name"] for e in claim_entities if _entity_in_text(e["name"], combined)]
    return {
        "evaluable": True,
        "has_match": len(matched) > 0,
        "matched_entities": matched,
        "claim_entities_checked": [e["name"] for e in claim_entities],
    }


def main():
    data = json.loads(Path("/tmp/entity_check_data.json").read_text())
    results = []
    for claim_id, d in data.items():
        for ev in d["evidence"]:
            if ev["stance"] == "irrelevant":
                continue  # only evaluate evidence that actually influences a verdict
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
    print(f"Evaluable (claim had >=1 extracted entity): {len(evaluable)}")
    print(f"NOT evaluable (claim had zero extracted entities): {len(not_evaluable)}")
    violations = [r for r in evaluable if not r["has_match"]]
    print(f"Entity-consistency violations flagged (no claim entity found in cited evidence): {len(violations)}")
    print()
    for r in results:
        flag = "SKIP(no entities)" if not r["evaluable"] else ("VIOLATION" if not r["has_match"] else "ok")
        print(f"[{flag:20s}] {r['claim_text'][:45]:45s} <- [{r['stance']:11s}] {r['evidence_title']}")

    Path("../research/results/entity_consistency_eval_20260814.json").write_text(json.dumps(results, indent=2))
    print("\nWrote research/results/entity_consistency_eval_20260814.json")


if __name__ == "__main__":
    main()
