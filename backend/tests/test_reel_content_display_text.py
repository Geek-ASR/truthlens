from app.pipeline.reel_content import _display_text


def test_strips_trailing_validation_note():
    raw = "The rule exists and Kejriwal criticized it.\n\n[VALIDATION NOTE: Some issue.]"
    assert _display_text(raw) == "The rule exists and Kejriwal criticized it."


def test_strips_validation_note_containing_a_python_list_repr():
    # Real bug found live (docs/CURRENT_ARCHITECTURE.md): a naive
    # non-greedy "[VALIDATION NOTE:...]" regex stopped at the FIRST "]"
    # it found, which was the closing bracket of the list repr inside the
    # note itself — leaving the note's tail visible on the slide.
    raw = (
        "The rule requires takedown within three hours.\n\n"
        "[VALIDATION NOTE: Numbers ['3065258', '69'] in reasoning_summary "
        "do not appear in any cited source passage.]"
    )
    assert _display_text(raw) == "The rule requires takedown within three hours."


def test_strips_internal_double_bracket_markup():
    raw = "Kejriwal criticized the rule [[evidence_id=abc123 | source=publisher=https://example.test]]."
    assert _display_text(raw) == "Kejriwal criticized the rule ."


def test_leaves_normal_text_untouched():
    raw = "The regulation was notified on February 10, 2026."
    assert _display_text(raw) == raw


def test_collapses_whitespace():
    raw = "Line one.\n\n\nLine   two."
    assert _display_text(raw) == "Line one. Line two."
