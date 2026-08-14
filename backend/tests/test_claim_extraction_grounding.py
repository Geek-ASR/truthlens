from app.pipeline.claim_extraction import _extraction_looks_grounded
from app.schemas.claim import ExtractedClaim

SOURCE_TEXT = """TRANSCRIPT:
The city council voted 7 to 2 last Tuesday to approve $50 million in transit funding."""


def _claim(text: str, source_quote: str | None, *, verifiable=True, claim_type="factual") -> ExtractedClaim:
    return ExtractedClaim(
        text=text,
        source_quote=source_quote,
        claim_type=claim_type,
        verifiable=verifiable,
        importance=0.8,
        extraction_confidence=0.8,
    )


def test_grounded_when_source_quote_actually_appears_in_source_text():
    claims = [_claim("The council approved $50M", "approve $50 million in transit funding")]
    assert _extraction_looks_grounded(claims, SOURCE_TEXT) is True


def test_ungrounded_when_source_quote_is_missing():
    # This is the exact failure mode observed live: real Instagram reel
    # content produced 8 schema-valid claims, every one with an empty
    # source_quote — including claims marked verifiable.
    claims = [_claim("Some hallucinated claim", None)]
    assert _extraction_looks_grounded(claims, SOURCE_TEXT) is False


def test_ungrounded_when_source_quote_does_not_match_source_text():
    claims = [_claim("Some hallucinated claim", "this text was never actually said")]
    assert _extraction_looks_grounded(claims, SOURCE_TEXT) is False


def test_no_verifiable_claims_is_not_treated_as_a_quality_failure():
    # Opinion-only content is a legitimate, correct extraction outcome —
    # nothing downstream acts on non-verifiable claims either way.
    claims = [_claim("This is just an opinion", None, verifiable=False, claim_type="opinion")]
    assert _extraction_looks_grounded(claims, SOURCE_TEXT) is True


def test_majority_grounded_passes_even_with_one_bad_claim():
    claims = [
        _claim("Real claim one", "voted 7 to 2 last Tuesday"),
        _claim("Real claim two", "approve $50 million in transit funding"),
        _claim("Hallucinated claim", None),
    ]
    assert _extraction_looks_grounded(claims, SOURCE_TEXT) is True


def test_minority_grounded_fails():
    claims = [
        _claim("Real claim", "voted 7 to 2 last Tuesday"),
        _claim("Hallucinated one", None),
        _claim("Hallucinated two", "fabricated text"),
        _claim("Hallucinated three", ""),
    ]
    assert _extraction_looks_grounded(claims, SOURCE_TEXT) is False


def test_case_and_whitespace_insensitive_matching():
    claims = [_claim("The council approved funding", "  APPROVE  $50 Million   In Transit Funding  ")]
    assert _extraction_looks_grounded(claims, SOURCE_TEXT) is True
