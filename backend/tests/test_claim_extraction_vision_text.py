from app.db.models import Reel
from app.pipeline.claim_extraction import _build_user_content


def _reel(**overrides) -> Reel:
    return Reel(source_url="https://example.test/p/abc/", **overrides)


def test_visible_text_or_graphics_is_included_and_labeled_like_ocr():
    # Real gap found live against a genuine photo post
    # (research_paper/benchmark or session notes: instagram.com/p/Dbrw0EPhFcU/):
    # OCR found nothing, but vision analysis of the same image correctly
    # read a specific on-screen claim into visible_text_or_graphics,
    # which was silently dropped because only scene_description was ever
    # included in the claim-extraction prompt.
    reel = _reel(
        vision_context={
            "scene_description": "A man in white robes stands next to another person.",
            "visible_text_or_graphics": "Yogi Adityanath government spent 94 crores on advertising in eight years.",
            "notable_entities": [],
        }
    )
    content = _build_user_content(reel)
    assert "ON-SCREEN TEXT (detected via image analysis):" in content
    assert "94 crores" in content
    assert "VISUAL CONTEXT (advisory, not evidence):" in content
    assert "A man in white robes" in content


def test_missing_visible_text_or_graphics_only_includes_scene_description():
    reel = _reel(vision_context={"scene_description": "Some scene.", "notable_entities": []})
    content = _build_user_content(reel)
    assert "ON-SCREEN TEXT (detected via image analysis):" not in content
    assert "VISUAL CONTEXT (advisory, not evidence):" in content
    assert "Some scene." in content


def test_caption_alone_is_still_sufficient():
    reel = _reel(caption_text="A caption with no vision context at all.")
    content = _build_user_content(reel)
    assert "POSTED CAPTION:" in content
    assert "A caption with no vision context at all." in content
