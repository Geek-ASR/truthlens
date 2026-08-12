from app.pipeline.reel_content import _headline_numbers_are_grounded, _numbers_in


def test_numbers_in_extracts_and_strips_trailing_punctuation():
    assert _numbers_in("Spent 4,000 crore in 2026.") == {"4,000", "2026"}


def test_numbers_in_empty_for_text_with_no_digits():
    assert _numbers_in("No numbers here at all.") == set()


def test_headline_grounded_when_number_matches_claim():
    claim = "The Yogi Adityanath government spent 4,000 crore rupees on advertising over eight years."
    headline = "Yogi Government Spent 4,000 Crore Rupees On Ads"
    assert _headline_numbers_are_grounded(headline, claim) is True


def test_headline_not_grounded_when_number_is_fabricated():
    # Real bug found live: the headline-generation model converted a
    # claim's "4,000 crore rupees" into "$1 Billion" -- an invented,
    # and wrong (4,000 crore is roughly $480M, not $1B), currency
    # conversion nobody asked for. HEADLINE_SYSTEM_PROMPT explicitly
    # forbids introducing a number not already in the claim text, and
    # the model violated it anyway -- this is the deterministic check
    # that actually catches it regardless of what the prompt says.
    claim = "The Yogi Adityanath government spent 4,000 crore rupees on advertising over eight years."
    headline = "India's Yogi Government Spent $1 Billion On Ads"
    assert _headline_numbers_are_grounded(headline, claim) is False


def test_headline_grounded_with_no_numbers_at_all():
    claim = "The government introduced a new rule about protest conduct."
    headline = "Government Introduces New Protest Conduct Rule"
    assert _headline_numbers_are_grounded(headline, claim) is True
