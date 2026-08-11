from app.pipeline.content_generation import _content_looks_complete
from app.schemas.content import ContentGenerationResult


def _result(**overrides) -> ContentGenerationResult:
    defaults = dict(
        slide1_claim_summary="Claim summary",
        slide3_evidence_explanation="Evidence explanation",
        slide3_key_fact="Key fact",
        slide4_conclusion_paragraph="Conclusion paragraph",
        caption_what_we_found="What we found",
        caption_why="Why",
    )
    defaults.update(overrides)
    return ContentGenerationResult(**defaults)


def test_complete_when_all_fields_have_real_content():
    assert _content_looks_complete(_result()) is True


def test_incomplete_when_any_field_is_an_empty_string():
    # This is the exact failure observed live: Ollama returned schema-valid
    # JSON with every field set to "" for a real UNVERIFIED verdict.
    assert _content_looks_complete(_result(slide4_conclusion_paragraph="")) is False


def test_incomplete_when_field_is_only_whitespace():
    assert _content_looks_complete(_result(caption_why="   ")) is False


def test_incomplete_when_all_fields_are_empty():
    empty = {
        "slide1_claim_summary": "",
        "slide3_evidence_explanation": "",
        "slide3_key_fact": "",
        "slide4_conclusion_paragraph": "",
        "caption_what_we_found": "",
        "caption_why": "",
    }
    assert _content_looks_complete(_result(**empty)) is False
