from datetime import datetime, timezone

from app.db.models import Claim, ClaimType, Reel, SourceTier, Verdict, VerdictLabel
from app.pipeline.content_generation import build_caption
from app.schemas.content import ContentGenerationResult


def _claim() -> Claim:
    return Claim(text="Government X banned all imports of Y yesterday.", claim_type=ClaimType.factual, verifiable=True)


def _reel() -> Reel:
    return Reel(source_url="https://instagram.com/reel/example")


def _verdict(label=VerdictLabel.MISLEADING) -> Verdict:
    return Verdict(verdict=label, confidence=0.8, reasoning_summary="...", cited_evidence_ids=[])


def _generated() -> ContentGenerationResult:
    return ContentGenerationResult(
        slide1_claim_summary="Government X banned all imports of Y yesterday",
        slide3_evidence_explanation="Official records show a partial restriction, not a total ban.",
        slide3_key_fact="The ban is partial.",
        slide4_conclusion_paragraph="The reel misstates the scope of a real policy.",
        caption_what_we_found="The claim overstates the scope of the policy.",
        caption_why="Ministry records describe a partial restriction announced two weeks earlier.",
    )


def test_caption_includes_all_required_sections():
    from app.db.models import Source

    source = Source(
        url="https://example-gov.test/report",
        title="Official report",
        publisher="Ministry of Trade",
        source_type=SourceTier.primary_government,
        full_text_storage_key="k",
        relevant_passage="p",
        reliability_score=0.9,
        reliability_breakdown={},
        retrieved_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )

    caption = build_caption(
        claim=_claim(), verdict=_verdict(), reel=_reel(), generated=_generated(), caption_sources=[source]
    )

    assert "FACT CHECK" in caption
    assert "MISLEADING" in caption
    assert "Ministry of Trade" in caption
    assert "https://example-gov.test/report" in caption
    assert "https://instagram.com/reel/example" in caption
    assert "#FactCheck" in caption
    # Sensational/insulting language must never appear (product spec §6).
    for banned_phrase in ("idiot", "lying", "stupid", "obviously fake"):
        assert banned_phrase not in caption.lower()


def test_caption_handles_no_sources_found_without_blank_section():
    caption = build_caption(
        claim=_claim(),
        verdict=_verdict(VerdictLabel.UNVERIFIED),
        reel=_reel(),
        generated=_generated(),
        caption_sources=[],
    )

    assert "No corroborating sources were found" in caption
