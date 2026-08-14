"""Benchmark-collection candidate tracker (governing brief Step 5;
research/BENCHMARK_COLLECTION_GUIDE.md). A candidate is NOT benchmark
data until it reaches ELIGIBLE — nothing here is silently promoted to
research/dataset/*.jsonl automatically. This is tooling to make the
already-measured ~8% real-world sourcing hit rate (DATASET_CARD.md)
efficient to work through manually/semi-automatically, not a scraper.

Storage: research/dataset/candidates_v2.jsonl, one JSON object per line,
append-only in spirit (update_status rewrites the whole file with the
one candidate's fields changed, same pattern as items.jsonl's own
"frozen once written" discipline for promoted items -- candidates
themselves are allowed to change status, that's the whole point of the
tracker, but candidate_id is stable once assigned and history isn't
silently discarded: every status transition is appended to the
candidate's own `history` list, not overwritten).
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CANDIDATES_PATH = _REPO_ROOT / "research" / "dataset" / "candidates_v2.jsonl"

ELIGIBILITY_STATES = (
    "DISCOVERED",
    "ARTICLE_FOUND",
    "SOCIAL_REFERENCE_FOUND",
    "MEDIA_RETRIEVABLE",
    "GROUND_TRUTH_VERIFIED",
    "ELIGIBLE",
    "REJECTED",
    "UNRESOLVED",
)

# The order a candidate is expected to progress through on the way to
# ELIGIBLE -- enforced softly (a jump is logged, not blocked) since a
# well-documented fact-check article sometimes establishes several of
# these simultaneously and forcing a strict state machine would just
# encourage rubber-stamping intermediate states no one actually checked.
_PROGRESSION_ORDER = (
    "DISCOVERED",
    "ARTICLE_FOUND",
    "SOCIAL_REFERENCE_FOUND",
    "MEDIA_RETRIEVABLE",
    "GROUND_TRUTH_VERIFIED",
    "ELIGIBLE",
)


@dataclass
class Candidate:
    candidate_id: str
    factchecker: str | None = None
    factcheck_article: str | None = None
    social_url: str | None = None
    media_url: str | None = None
    media_status: str | None = None  # e.g. "live" / "taken_down" / "unknown"
    ground_truth_claim: str | None = None
    ground_truth_label: str | None = None
    claim_type: str | None = None
    language: str | None = None
    political_actor: str | None = None
    media_type: str | None = None  # "video" | "photo"
    publication_date: str | None = None
    factcheck_date: str | None = None
    cross_post_status: str | None = None  # "unknown" | "possible" | "verified" | "not_applicable"
    source_quality: str | None = None  # free-text note on factchecker credibility/specificity
    eligibility_status: str = "DISCOVERED"
    rejection_reason: str | None = None
    history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__


def _load_all() -> list[dict]:
    if not _CANDIDATES_PATH.exists():
        return []
    with open(_CANDIDATES_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


def _save_all(candidates: list[dict]) -> None:
    with open(_CANDIDATES_PATH, "w") as f:
        for c in candidates:
            f.write(json.dumps(c) + "\n")


def add_candidate(candidate: Candidate) -> Candidate:
    candidates = _load_all()
    if any(c["candidate_id"] == candidate.candidate_id for c in candidates):
        raise ValueError(f"candidate_id {candidate.candidate_id!r} already exists")
    candidate.history.append(
        {"status": candidate.eligibility_status, "at": datetime.now(timezone.utc).isoformat(), "note": "created"}
    )
    candidates.append(candidate.to_dict())
    _save_all(candidates)
    return candidate


def update_status(candidate_id: str, new_status: str, *, note: str = "", rejection_reason: str | None = None) -> dict:
    if new_status not in ELIGIBILITY_STATES:
        raise ValueError(f"{new_status!r} is not a valid eligibility state: {ELIGIBILITY_STATES}")
    candidates = _load_all()
    for c in candidates:
        if c["candidate_id"] == candidate_id:
            c["eligibility_status"] = new_status
            if rejection_reason is not None:
                c["rejection_reason"] = rejection_reason
            c.setdefault("history", []).append(
                {"status": new_status, "at": datetime.now(timezone.utc).isoformat(), "note": note}
            )
            _save_all(candidates)
            return c
    raise ValueError(f"candidate_id {candidate_id!r} not found")


def list_candidates(status: str | None = None) -> list[dict]:
    candidates = _load_all()
    if status is None:
        return candidates
    return [c for c in candidates if c["eligibility_status"] == status]


def composition_of_eligible() -> dict:
    """Quick label/claim-type/language counts among ELIGIBLE candidates
    only -- NOT a substitute for the real benchmark composition report
    (composition_report.py), which reads actual frozen dataset files.
    Useful while sourcing, to see live whether a new candidate closes a
    known gap (e.g. TRUE-labeled items) before spending more effort."""
    eligible = list_candidates("ELIGIBLE")
    counts: dict[str, dict[str, int]] = {"ground_truth_label": {}, "claim_type": {}, "language": {}}
    for c in eligible:
        for field_name in counts:
            value = c.get(field_name) or "unknown"
            counts[field_name][value] = counts[field_name].get(value, 0) + 1
    return counts
