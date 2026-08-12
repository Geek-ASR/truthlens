from app.db.models import ClaimStatus, ClaimType, VerdictLabel
from app.db.models import Claim as ClaimModel
from app.db.models import Verdict as VerdictModel
from app.pipeline.overall_verdict import derive_overall_verdict


def _claim(text: str, importance: float = 0.5, status=ClaimStatus.researched) -> ClaimModel:
    return ClaimModel(text=text, claim_type=ClaimType.factual, verifiable=True, importance=importance, status=status)


def _verdict(label: VerdictLabel) -> VerdictModel:
    return VerdictModel(verdict=label, confidence=0.8, reasoning_summary="...", cited_evidence_ids=[])


def test_all_true_claims_yield_overall_true():
    pairs = [(_claim("A"), _verdict(VerdictLabel.TRUE)), (_claim("B"), _verdict(VerdictLabel.TRUE))]
    result = derive_overall_verdict(pairs)
    assert result.label == VerdictLabel.TRUE


def test_mix_of_true_and_false_yields_misleading():
    # The exact example from the product spec: Claim1 TRUE, Claim2 TRUE,
    # Claim3 FALSE -> Overall MISLEADING.
    pairs = [
        (_claim("A"), _verdict(VerdictLabel.TRUE)),
        (_claim("B"), _verdict(VerdictLabel.TRUE)),
        (_claim("C"), _verdict(VerdictLabel.FALSE)),
    ]
    result = derive_overall_verdict(pairs)
    assert result.label == VerdictLabel.MISLEADING


def test_all_false_yields_overall_false():
    pairs = [(_claim("A"), _verdict(VerdictLabel.FALSE)), (_claim("B"), _verdict(VerdictLabel.FALSE))]
    result = derive_overall_verdict(pairs)
    assert result.label == VerdictLabel.FALSE


def test_all_unverified_yields_overall_unverified():
    pairs = [(_claim("A"), _verdict(VerdictLabel.UNVERIFIED)), (_claim("B"), _verdict(VerdictLabel.UNVERIFIED))]
    result = derive_overall_verdict(pairs)
    assert result.label == VerdictLabel.UNVERIFIED


def test_no_resolved_claims_yields_unverified_not_a_crash():
    result = derive_overall_verdict([])
    assert result.label == VerdictLabel.UNVERIFIED
    assert result.claim_verdicts == []


def test_research_failed_claims_are_excluded_from_the_decision():
    pairs = [
        (_claim("A"), _verdict(VerdictLabel.TRUE)),
        (_claim("B", status=ClaimStatus.research_failed), None),
    ]
    result = derive_overall_verdict(pairs)
    assert result.label == VerdictLabel.TRUE
    assert result.unresolved_claim_count == 1
    assert len(result.claim_verdicts) == 1
