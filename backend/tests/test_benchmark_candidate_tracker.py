"""research/BENCHMARK_COLLECTION_GUIDE.md tooling. Uses tmp_path for
storage so these tests never touch the real
research/dataset/candidates_v2.jsonl file."""
import multiprocessing

import pytest

from research.benchmark_v2 import candidate_tracker as tracker


@pytest.fixture(autouse=True)
def _isolated_candidates_file(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "_CANDIDATES_PATH", tmp_path / "candidates_v2.jsonl")
    monkeypatch.setattr(tracker, "_LOCK_PATH", tmp_path / ".candidates_v2.lock")
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


def _worker_add_many(candidates_path, lock_path, prefix, n):
    """Module-level (not a local closure) so multiprocessing can pickle
    and run it in a genuinely separate process -- a real regression test
    for the exact live crash this locking fix was built for: two
    separate processes doing add_candidate()/update_status() against the
    same file concurrently lost a write outright, crashing a
    multi-hour mass-sourcing pipeline with a "candidate_id not found"
    error on its very next call."""
    import research.benchmark_v2.candidate_tracker as t
    t._CANDIDATES_PATH = candidates_path
    t._LOCK_PATH = lock_path
    for i in range(n):
        t.add_candidate(t.Candidate(candidate_id=f"cand-{prefix}-{i}", factchecker="test"))


def test_concurrent_writes_from_separate_processes_lose_nothing(tmp_path):
    # Uses real, separate OS processes (not threads/asyncio tasks within
    # one process) -- the actual shape of the live crash this test
    # guards against: a mass-sourcing pipeline process and a second,
    # independently-invoked script (spot-check/promotion) both writing
    # to the same candidates_v2.jsonl at the same time.
    candidates_path = tmp_path / "candidates_v2.jsonl"
    lock_path = tmp_path / ".candidates_v2.lock"
    ctx = multiprocessing.get_context("spawn")
    n_per_process = 15
    processes = [
        ctx.Process(target=_worker_add_many, args=(candidates_path, lock_path, "A", n_per_process)),
        ctx.Process(target=_worker_add_many, args=(candidates_path, lock_path, "B", n_per_process)),
    ]
    for p in processes:
        p.start()
    for p in processes:
        p.join(timeout=30)
        assert p.exitcode == 0

    with open(candidates_path) as f:
        ids = [line for line in f if line.strip()]
    assert len(ids) == 2 * n_per_process
