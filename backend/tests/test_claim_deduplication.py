"""research/RESEARCH_ROADMAP_V2.md Phase 2, governing brief Step 6.
Regression coverage for item-0004's real, previously-diagnosed-but
-unfixed failure mode: 7 near-duplicate claims from noisy OCR-frame
variants of the same on-screen text (research_paper/main.tex Section X,
"a new, unfixed failure mode -- no existing check evaluates cross-claim
redundancy"). The similarity threshold (0.92) is empirically chosen —
see _deduplicate_claims's own comment for the real SequenceMatcher
ratios that set it, including the exact "nail batons" example the
governing brief itself warns must NOT be merged."""
from app.pipeline.claim_extraction import _deduplicate_claims
from app.schemas.claim import ExtractedClaim


def _claim(text: str, claim_type: str = "factual") -> ExtractedClaim:
    return ExtractedClaim(text=text, claim_type=claim_type, verifiable=True, importance=0.5, extraction_confidence=0.5)


def test_no_duplicates_keeps_every_claim():
    claims = [_claim("Police used batons"), _claim("The mayor resigned"), _claim("Funding was cut")]
    result = _deduplicate_claims(claims)
    assert len(result) == 3


def test_punctuation_noise_variants_are_merged():
    claims = [_claim("Police used batons on protesters"), _claim("Police used batons on protesters!")]
    result = _deduplicate_claims(claims)
    assert len(result) == 1


def test_materially_different_claims_are_not_merged():
    """The exact example the governing brief itself warns against
    incorrectly merging -- "nail batons" is a different, more specific
    claim than "batons", not noise on the same claim."""
    claims = [_claim("Police used batons"), _claim("Police used nail batons")]
    result = _deduplicate_claims(claims)
    assert len(result) == 2
    assert {c.text for c in result} == {"Police used batons", "Police used nail batons"}


def test_different_claim_type_is_never_merged_even_if_text_is_identical():
    claims = [_claim("The scheme will fail", claim_type="prediction"), _claim("The scheme will fail", claim_type="opinion")]
    result = _deduplicate_claims(claims)
    assert len(result) == 2


def test_merging_keeps_the_longer_variant():
    claims = [
        _claim("Police used batons on protesters"),
        _claim("Police used batons on the protesters"),
    ]
    result = _deduplicate_claims(claims)
    assert len(result) == 1
    assert result[0].text == "Police used batons on the protesters"


def test_seven_ocr_frame_variants_collapse_to_one_real_claim():
    """Reproduces the actual item-0004 shape: many near-identical reads
    of the same on-screen text across consecutive video frames, each
    with minor OCR noise."""
    variants = [
        "Police used a nail-fitted baton",
        "Police used a nail-fitted baton.",
        "Police used a nail fitted baton",
        "police used a nail-fitted baton",
        "Police used a nail-fitted  baton",
        "Police used a nail-fitted baton!",
        "Police  used a nail-fitted baton",
    ]
    claims = [_claim(v) for v in variants]
    result = _deduplicate_claims(claims)
    assert len(result) == 1


def test_preserves_extraction_order_for_non_duplicate_claims():
    claims = [_claim("First claim"), _claim("Second claim"), _claim("Third claim")]
    result = _deduplicate_claims(claims)
    assert [c.text for c in result] == ["First claim", "Second claim", "Third claim"]


def test_empty_list_returns_empty_list():
    assert _deduplicate_claims([]) == []
