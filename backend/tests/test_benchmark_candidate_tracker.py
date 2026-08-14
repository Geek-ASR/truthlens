"""research/BENCHMARK_COLLECTION_GUIDE.md tooling. Uses tmp_path for
storage so these tests never touch the real
research/dataset/candidates_v2.jsonl file."""
import pytest

from research.benchmark_v2 import candidate_tracker as tracker


@pytest.fixture(autouse=True)
def _isolated_candidates_file(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "_CANDIDATES_PATH", tmp_path / "candidates_v2.jsonl")
    yield


def test_add_candidate_persists_and_records_creation_history():
    tracker.add_candidate(tracker.Candidate(candidate_id="cand-001", factchecker="boomlive.in"))
    candidates = tracker.list_candidates()
    assert len(candidates) == 1
    assert candidates[0]["candidate_id"] == "cand-001"
    assert candidates[0]["eligibility_status"] == "DISCOVERED"
    assert len(candidates[0]["history"]) == 1


def test_duplicate_candidate_id_is_rejected():
    tracker.add_candidate(tracker.Candidate(candidate_id="cand-001"))
    with pytest.raises(ValueError):
        tracker.add_candidate(tracker.Candidate(candidate_id="cand-001"))


def test_update_status_appends_history_rather_than_replacing_it():
    tracker.add_candidate(tracker.Candidate(candidate_id="cand-001"))
    tracker.update_status("cand-001", "ARTICLE_FOUND", note="found on boomlive.in")
    tracker.update_status("cand-001", "ELIGIBLE", note="all checks passed")
    updated = tracker.list_candidates()[0]
    assert updated["eligibility_status"] == "ELIGIBLE"
    assert [h["status"] for h in updated["history"]] == ["DISCOVERED", "ARTICLE_FOUND", "ELIGIBLE"]


def test_update_status_rejects_unknown_state():
    tracker.add_candidate(tracker.Candidate(candidate_id="cand-001"))
    with pytest.raises(ValueError):
        tracker.update_status("cand-001", "NOT_A_REAL_STATE")


def test_update_status_unknown_candidate_id_raises_rather_than_silently_no_op():
    with pytest.raises(ValueError):
        tracker.update_status("does-not-exist", "ELIGIBLE")


def test_rejection_reason_is_recorded_when_rejected():
    tracker.add_candidate(tracker.Candidate(candidate_id="cand-001"))
    tracker.update_status("cand-001", "REJECTED", rejection_reason="post no longer live")
    rejected = tracker.list_candidates("REJECTED")
    assert len(rejected) == 1
    assert rejected[0]["rejection_reason"] == "post no longer live"


def test_list_candidates_filters_by_status():
    tracker.add_candidate(tracker.Candidate(candidate_id="cand-001"))
    tracker.add_candidate(tracker.Candidate(candidate_id="cand-002"))
    tracker.update_status("cand-002", "ELIGIBLE")
    assert [c["candidate_id"] for c in tracker.list_candidates("ELIGIBLE")] == ["cand-002"]
    assert [c["candidate_id"] for c in tracker.list_candidates("DISCOVERED")] == ["cand-001"]


def test_composition_of_eligible_only_counts_eligible_candidates():
    tracker.add_candidate(
        tracker.Candidate(candidate_id="cand-001", ground_truth_label="TRUE", claim_type="statistic", language="en")
    )
    tracker.add_candidate(
        tracker.Candidate(candidate_id="cand-002", ground_truth_label="FALSE", claim_type="provenance", language="en")
    )
    tracker.update_status("cand-001", "ELIGIBLE")
    composition = tracker.composition_of_eligible()
    assert composition["ground_truth_label"] == {"TRUE": 1}
    assert composition["claim_type"] == {"statistic": 1}
