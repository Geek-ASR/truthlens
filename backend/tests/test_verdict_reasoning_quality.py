from app.pipeline.verdict import _reasoning_looks_substantive


def test_real_prose_is_substantive():
    text = "The government notification confirms a three-hour takedown requirement applies here."
    assert _reasoning_looks_substantive(text) is True


def test_pure_citation_markup_is_not_substantive():
    # Real bug found live (docs/CURRENT_ARCHITECTURE.md): a verdict's
    # entire reasoning_summary was made of citation markup blocks with no
    # actual prose — schema-valid (non-empty string) but explains nothing.
    text = (
        "[[evidence_id=626c6f2f-923a-420d-ad8e-ea94a730d977 | source=publisher=https://example.test]], "
        "[[evidence_id=191ada58-1d1c-4526-8e9a-6b26a866cf41 | source=publisher=https://example2.test]]"
    )
    assert _reasoning_looks_substantive(text) is False


def test_prose_with_one_inline_citation_is_still_substantive():
    text = (
        "This source directly supports the claim about the takedown rule "
        "[[evidence_id=abc123 | source=publisher=https://example.test]]."
    )
    assert _reasoning_looks_substantive(text) is True


def test_empty_string_is_not_substantive():
    assert _reasoning_looks_substantive("") is False
