"""Coverage for the deterministic claim-provenance inference added in
research/RESEARCH_ROADMAP_V2.md Phase 2 — source_modalities and
provenance_detail are derived by substring-matching source_quote against
the reel's raw inputs, never asked of the LLM, and verifiability is a
richer derivation of the pre-existing boolean `verifiable` column."""
from app.db.models import ClaimVerifiability, Reel
from app.pipeline.claim_extraction import _infer_source_modalities, _infer_verifiability
from app.schemas.claim import ExtractedClaim


def _reel(**kwargs) -> Reel:
    return Reel(source_url="https://instagram.com/reel/provenance-test", **kwargs)


def _claim(source_quote: str | None, **kwargs) -> ExtractedClaim:
    defaults = dict(text="a claim", claim_type="factual", verifiable=True, importance=0.5, extraction_confidence=0.7)
    defaults.update(kwargs)
    return ExtractedClaim(source_quote=source_quote, **defaults)


def test_no_source_quote_yields_no_modality_and_no_detail():
    modalities, detail = _infer_source_modalities(_claim(None), _reel())
    assert modalities == []
    assert detail is None


def test_quote_matched_in_transcript_only():
    reel = _reel(transcript="The council approved fifty million in funding.")
    modalities, detail = _infer_source_modalities(_claim("approved fifty million"), reel)
    assert modalities == ["AUDIO"]
    assert detail == {"modality": "AUDIO", "matched_text": "approved fifty million"}


def test_quote_matched_in_ocr_records_segment_index():
    reel = _reel(ocr_text=[{"frame_ts": 0, "text": "unrelated"}, {"frame_ts": 3, "text": "Funding: $50 million"}])
    modalities, detail = _infer_source_modalities(_claim("Funding: $50 million"), reel)
    assert modalities == ["OCR"]
    assert detail == {"modality": "OCR", "segment_index": 1, "matched_text": "Funding: $50 million"}


def test_quote_matched_in_caption():
    reel = _reel(caption_text="Breaking: fifty million approved today")
    modalities, detail = _infer_source_modalities(_claim("fifty million approved"), reel)
    assert modalities == ["CAPTION"]


def test_quote_matched_in_vision_visible_text():
    reel = _reel(vision_context={"visible_text_or_graphics": "Spent ₹94 crores on advertising"})
    modalities, detail = _infer_source_modalities(_claim("₹94 crores on advertising"), reel)
    assert modalities == ["VISION"]


def test_quote_matched_in_multiple_modalities_returns_all_and_multimodal_detail():
    reel = _reel(
        transcript="the mayor announced fifty million today",
        caption_text="fifty million announced by the mayor",
    )
    modalities, detail = _infer_source_modalities(_claim("fifty million"), reel)
    assert set(modalities) == {"AUDIO", "CAPTION"}
    assert detail["modality"] == "MULTIMODAL"
    assert set(detail["matched_in"]) == {"AUDIO", "CAPTION"}


def test_quote_matching_is_case_and_whitespace_insensitive():
    reel = _reel(transcript="The Council   APPROVED  fifty million.")
    modalities, _ = _infer_source_modalities(_claim("council approved fifty million"), reel)
    assert modalities == ["AUDIO"]


def test_quote_present_but_not_matching_any_input_yields_empty():
    reel = _reel(transcript="something completely unrelated")
    modalities, detail = _infer_source_modalities(_claim("a quote that appears nowhere"), reel)
    assert modalities == []
    assert detail is None


def test_verifiability_true_and_factual_is_verifiable():
    assert _infer_verifiability(_claim("q", verifiable=True, claim_type="factual")) == ClaimVerifiability.verifiable


def test_verifiability_false_is_not_verifiable_regardless_of_type():
    assert (
        _infer_verifiability(_claim("q", verifiable=False, claim_type="factual"))
        == ClaimVerifiability.not_verifiable
    )


def test_verifiability_true_but_non_factual_is_uncertain_not_silently_downgraded():
    """The pre-existing boolean `verifiable` column silently collapses
    this case to False (verifiable and claim_type == "factual") with no
    trace it was ever ambiguous. verifiability distinguishes it."""
    assert (
        _infer_verifiability(_claim("q", verifiable=True, claim_type="opinion"))
        == ClaimVerifiability.uncertain
    )
