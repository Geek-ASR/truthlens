"""Phase 8 (research/RESEARCH_ROADMAP_V2.md): re-run the adversarial
validator benchmark against the NEW combined check set -- Checks 6
(temporal, Phase 5) and 7 (entity, Phase 4), both integrated into
production this session -- which the original 30-case benchmark
(build_and_run.py) has ZERO coverage of: its Case/add() helper never
passed claim_time_reference/claim_entities, so Checks 6/7 were
structurally dormant against every one of those 30 cases (matches
validate_verdict()'s own documented backward-compatibility design, not
a bug).

Imports the original 30 cases unchanged (build_cases(), not
reimplemented) and adds real new cases targeting exactly the 2 new
checks, honest about scope: Step 18 names 20 adversarial categories,
several of which (OCR/audio corruption, AI-generated image, edited
video, mixed-language, multiple claims) are upstream pipeline concerns
this validator-only benchmark cannot test at all (Phase 11's later,
broader scope) -- not padded in here to inflate a count.

One case is a direct, real gap-closing test: E1 in the original
benchmark ("wrong entity: cited evidence about a different,
similarly-named organization") was explicitly marked
checkable_by_current_checks=False -- a real, disclosed gap at the time
it was written. E1v2 here is the SAME scenario, this time with
claim_entities actually wired through, to directly test whether Check 7
closes that specific, previously-diagnosed gap -- not a new invented
case, a re-test of an old, named limitation.

Run: cd backend && .venv/bin/python research/validator_benchmark/build_and_run_v2.py
"""
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from app.db.models import Source, SourceTier, ValidationStatus, VerdictLabel  # noqa: E402
from app.pipeline.validation import validate_verdict  # noqa: E402
from app.schemas.verdict import VerdictProposal  # noqa: E402
from research.validator_benchmark.build_and_run import Case, _source, build_cases  # noqa: E402


def _dated_source(passage: str, publication_date) -> Source:
    return Source(
        id=uuid.uuid4(), url="https://example-real-domain.test/article", title="Test source",
        source_type=SourceTier.established_news, full_text_storage_key="sources/fulltext/x.txt",
        relevant_passage=passage, reliability_score=0.7, reliability_breakdown={},
        retrieved_at=datetime.now(timezone.utc), publication_date=publication_date,
        created_at=datetime.now(timezone.utc),
    )


def build_new_cases() -> list[Case]:
    cases = []

    # ---- P: temporal mismatch, Check 6 (Phase 5, new this session) ----
    # Real "old footage presented as current" shape: claim asserts an
    # explicit date, cited source predates it by well over the 2-day
    # tolerance.
    for i, (claim_date, pub_offset_days) in enumerate([("August 4, 2026", -400), ("March 15, 2026", -900)]):
        eid = uuid.uuid4()
        pub_date = datetime(2026, 8, 4, tzinfo=timezone.utc) + timedelta(days=pub_offset_days)
        cases.append(Case(
            case_id=f"P{i+1}", category="P", split="dev" if i == 0 else "test",
            description=f"Old footage presented as current: claim asserts {claim_date}, cited source predates it by {-pub_offset_days} days",
            should_be_flagged=True, checkable_by_current_checks=True,
            proposal=VerdictProposal(
                verdict=VerdictLabel.FALSE, confidence=0.8,
                reasoning_summary="The footage shown is confirmed by this source.", cited_evidence_ids=[eid],
            ),
            evidence_by_id={eid: object()},
            source_by_evidence_id={eid: _dated_source("Footage of the event described.", pub_date)},
        ))
        cases[-1].claim_time_reference = claim_date  # dynamically attached -- see runner below

    # ---- P-negative: source postdates the claim (normal case), Check 6 must NOT fire ----
    eid = uuid.uuid4()
    pub_date = datetime(2026, 8, 10, tzinfo=timezone.utc)
    case = Case(
        case_id="P3-negative", category="P", split="dev",
        description="Normal case: source published AFTER the claimed date -- must NOT be flagged as temporal mismatch",
        should_be_flagged=False, checkable_by_current_checks=True,
        proposal=VerdictProposal(
            verdict=VerdictLabel.TRUE, confidence=0.8,
            reasoning_summary="The event is confirmed by this later report.", cited_evidence_ids=[eid],
        ),
        evidence_by_id={eid: object()},
        source_by_evidence_id={eid: _dated_source("The event took place as described.", pub_date)},
    )
    case.claim_time_reference = "August 4, 2026"
    cases.append(case)

    # ---- Q: entity mismatch, Check 7 (Phase 4, new this session) ----
    for i, (claim_entity, entity_type, wrong_org_text) in enumerate([
        ("Delhi Police", "Organization", "Police in Burdwan, West Bengal were filmed beating student protesters."),
        ("Karni Sena", "organization", "Sri Ram Sena is a Hindu nationalist organisation, unrelated to the claim."),
    ]):
        eid = uuid.uuid4()
        case = Case(
            case_id=f"Q{i+1}", category="Q", split="dev" if i == 0 else "test",
            description=f"Wrong entity: claim about {claim_entity!r}, cited evidence about a different, unrelated organization",
            should_be_flagged=True, checkable_by_current_checks=True,
            proposal=VerdictProposal(
                verdict=VerdictLabel.FALSE, confidence=0.8,
                reasoning_summary="The organization's action is confirmed by this source.", cited_evidence_ids=[eid],
            ),
            evidence_by_id={eid: object()},  # stance read only when claim_entities has an evaluable entity -- see note below; this object() is fine for cases where it's never touched, but Check 7 DOES read .stance here, so use a real stance-bearing stand-in
            source_by_evidence_id={eid: _source(wrong_org_text)},
        )
        case.claim_entities = [{"name": claim_entity, "type": entity_type}]
        cases.append(case)

    # ---- E1v2: direct re-test of the ORIGINAL benchmark's E1 case (marked
    # checkable_by_current_checks=False when written) -- same evidence
    # text, same reasoning, this time with claim_entities actually wired
    # through, to test whether Check 7 closes that specific, previously
    # -diagnosed real gap.
    eid = uuid.uuid4()
    case = Case(
        case_id="E1v2-retest", category="E", split="test",
        description="Direct re-test of original E1 (previously checkable_by_current_checks=False) with claim_entities now wired through",
        should_be_flagged=True, checkable_by_current_checks=True,
        proposal=VerdictProposal(
            verdict=VerdictLabel.MOSTLY_FALSE, confidence=0.7,
            reasoning_summary="The source confirms the organization's statement was false.", cited_evidence_ids=[eid],
        ),
        evidence_by_id={eid: object()},
        source_by_evidence_id={eid: _source(
            "A spokesperson for the National Youth Front (not the organization named in the claim) denied the allegation."
        )},
    )
    case.claim_entities = [{"name": "Youth Congress", "type": "organization"}]
    cases.append(case)

    return cases


def main() -> None:
    original_cases = build_cases()  # claim_time_reference/claim_entities default to None -- unchanged from the original file's own 30 cases
    new_cases = build_new_cases()
    all_cases = original_cases + new_cases

    results = []
    for c in all_cases:
        # Check 7 reads evidence.stance only when claim_entities has an
        # evaluable-type entity (validate_verdict's own backward
        # -compatibility design) -- for the 4 new cases that DO set
        # claim_entities, the plain object() placeholder would crash on
        # that read, so give those specific cases a real stance-bearing
        # stand-in instead of the original benchmark's bare object().
        if c.claim_entities:
            from types import SimpleNamespace
            from app.db.models import EvidenceStance
            c.evidence_by_id = {eid: SimpleNamespace(stance=EvidenceStance.contradicts) for eid in c.evidence_by_id}

        outcome = validate_verdict(
            c.proposal, c.evidence_by_id, c.source_by_evidence_id,
            c.claim_time_reference, c.claim_entities,
        )
        flagged = outcome.status != ValidationStatus.passed
        results.append({
            "case_id": c.case_id, "category": c.category, "split": c.split,
            "description": c.description, "should_be_flagged": c.should_be_flagged,
            "checkable_by_current_checks": c.checkable_by_current_checks,
            "flagged": flagged, "validation_status": outcome.status.value,
            "correct": flagged == c.should_be_flagged,
        })

    for split in ("dev", "test"):
        split_results = [r for r in results if r["split"] == split]
        tp = sum(1 for r in split_results if r["should_be_flagged"] and r["flagged"])
        fp = sum(1 for r in split_results if not r["should_be_flagged"] and r["flagged"])
        fn = sum(1 for r in split_results if r["should_be_flagged"] and not r["flagged"])
        tn = sum(1 for r in split_results if not r["should_be_flagged"] and not r["flagged"])
        n = len(split_results)
        precision = tp / (tp + fp) if (tp + fp) else float("nan")
        recall = tp / (tp + fn) if (tp + fn) else float("nan")
        print(f"=== {split.upper()} (n={n}) === TP={tp} FP={fp} FN={fn} TN={tn} Precision={precision:.1%} Recall={recall:.1%}")

    print("\n=== New-case detail (P/Q/E1v2) ===")
    for r in results:
        if r["category"] in ("P", "Q") or r["case_id"] == "E1v2-retest":
            mark = "OK " if r["correct"] else "ERR"
            print(f"[{mark}] {r['case_id']:15s} should_flag={r['should_be_flagged']!s:5s} flagged={r['flagged']!s:5s} status={r['validation_status']}")

    out_path = Path(__file__).resolve().parents[3] / "research" / "results" / "validator_synthetic_benchmark_v2_20260818.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {out_path}")
    print(f"Total cases: {len(results)} ({len(original_cases)} original + {len(new_cases)} new)")


if __name__ == "__main__":
    main()
