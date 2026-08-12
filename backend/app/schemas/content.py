from pydantic import BaseModel, Field


class ContentGenerationResult(BaseModel):
    """Structured output for the content_generation LLM stage. Source
    names/URLs are deliberately NOT part of this schema — the caption's
    SOURCES section is assembled in code directly from `sources` rows, so
    the model can never introduce a source that wasn't actually
    retrieved (docs/FACT_CHECK_METHODOLOGY.md §7)."""

    slide1_claim_summary: str = Field(max_length=140, description="Short claim summary for the poster slide")
    slide3_evidence_explanation: str = Field(
        max_length=400, description="Concise neutral explanation of what the evidence shows"
    )
    slide3_key_fact: str = Field(max_length=140, description="One-sentence factual takeaway")
    slide4_conclusion_paragraph: str = Field(
        max_length=400, description="Short paragraph explaining the verdict for the conclusion slide"
    )
    caption_what_we_found: str = Field(max_length=600)
    caption_why: str = Field(max_length=800)


class HeadlineResult(BaseModel):
    """Structured output for the headline-generation LLM stage (slide 1).
    highlight_phrases are validated as real substrings of `headline` by
    the caller (app/pipeline/reel_content.py) — any phrase that isn't a
    verbatim substring is dropped rather than trusted, so a model that
    ignores the instruction just loses highlighting, not correctness."""

    headline: str = Field(max_length=180)
    highlight_phrases: list[str] = Field(default_factory=list, max_length=3)


class OverallWhyResult(BaseModel):
    """Structured output for the overall-verdict-explanation LLM stage
    (slide 4 / caption WHY). The overall verdict label itself is NOT part
    of this schema — it's computed deterministically
    (app/pipeline/overall_verdict.py) and only handed to this stage to
    explain, never to decide."""

    why_paragraph: str = Field(max_length=700)
