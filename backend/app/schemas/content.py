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
