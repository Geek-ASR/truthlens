# MULTIMODAL_EVALUATION_V2.md — Phase 3

Status: 2026-08-18. Successor to `MULTIMODAL_EVALUATION.md` (original
3-condition result, `n=6`), left unedited per this program's standing
rule. `research/RESEARCH_ROADMAP_V2.md` Phase 3 / Step 7: re-run the
modality-coverage experiment across the full 8-combination powerset the
step names, and measure per-modality precision, not just coverage.

## What was built

The original 3-condition experiment (`research/multimodal/
run_claim_coverage.py`) bundled transcript(audio) and caption together
as one always-on "text" signal, disclosed at the time as an honest
simplification, not a claim that the pipeline itself couldn't do more.
It could: `app.pipeline.claim_extraction._build_user_content()` already
checks transcript, OCR, caption, and vision_context as 4 independent
`if` blocks. `backend/research/multimodal_v2/run_8way_coverage.py` keeps
caption always on (user-authored text, not a system-*sensed* modality —
there's no pipeline stage that "extracts" it, unlike the other 3) and
toggles audio/OCR/vision independently: 2³ = 8 combinations, matching
Step 7's own count exactly, reusing `_build_user_content()` directly
(imported, not reimplemented).

## Real result 1: claim coverage against ground truth (comparable to the original 33.3%/16.7%/0.0% metric)

Same 8 real DEV-split items as the original evaluation's pool. For each
condition, whether at least one extracted claim covers the item's own
`items.jsonl` ground-truth `claim_text` (same "same specific assertion"
human-judgment standard `METRICS.md` §2 already defines — manually
reviewed here, not string-matched):

| Condition | Items covered / 8 |
|---|---|
| caption_only | 2 (25.0%) |
| audio | 2 (25.0%) |
| ocr | 2 (25.0%) |
| **vision** | **3 (37.5%)** |
| audio+ocr | 2 (25.0%) |
| audio+vision | 2 (25.0%) |
| ocr+vision | 1 (12.5%) |
| audio+ocr+vision | 2 (25.0%) |

`vision` alone scores highest — directionally consistent with the
original evaluation's own finding that vision-inclusive conditions help
— but the overall pattern is **not** a clean "more modalities is
strictly better" curve: `ocr+vision` (12.5%) scores below every
single-signal condition, and the full `audio+ocr+vision` condition
(25.0%) does not outscore `vision` alone. Reported as found, not
smoothed into a monotonic story — consistent with the original
evaluation's own already-disclosed non-monotonic surprise (`text_ocr`
scoring below `text_only`).

**Two items never got their ground-truth claim covered by any of the 8
conditions**: the CJP/Jantar Mantar Islamic-slogans item (zero claims
extracted in every condition — the same garbled-transcript pattern
`EXP-011` already confirmed for other items) and, notably, **the
benchmark's one TRUE-labeled item** (the nail-fitted police baton claim)
— also zero claims extracted in every one of the 8 conditions this pass.
A third item (the masked-woman/Karni-Sena item) *did* produce 5 real
claims under `audio+ocr+vision`, but none of them cover the actual
ground-truth assertion (masked identity revealed amid misconduct) — the
extraction instead surfaced peripheral claims about the poster's
identity and generic civic sentiment from the caption. A real, disclosed
claim-coverage failure in `METRICS.md`'s own defined sense (Rule 5: a
claim extracted ≠ the checkworthy claim extracted), not the same failure
mode as the zero-claims items.

## Real result 2: groundedness rate is 0/90 — NOT the same metric as `METRICS.md`'s "Claim Precision," and a much stronger reconfirmation of EXP-012

This experiment also computed, per claim, whether its `source_quote`
verbatim-matches the item's real content (`_infer_source_modalities`,
the same deterministic check EXP-012 used). **Important correction,
made explicit here rather than silently**: this is a *groundedness/
provenance* signal, not `METRICS.md`'s own defined "Claim Precision"
(which requires human judgment against ground-truth checkworthy claims,
same as coverage above) — the two should not be conflated, and this
document's first draft internally mislabeled them before this
correction.

Real result: **0 of 90 real, non-empty claims across all 8 items and 8
conditions had a verbatim-matching `source_quote`.** This is not a bug
in this script — spot-checked directly (claim texts are real, non-empty,
substantive: e.g. "#CJP protesters allegedly pelted stones at a new
hydrogen train", "This isn't democracy, it's vandalism.") — it
independently and far more robustly reconfirms EXP-012's tentative n=12
null finding at n=90, across every modality condition tested, not just
one. **This is now a well-established, systematic property of current
`claim_extraction` behavior with llama3.2 on real content**: the model
essentially never populates `source_quote`, regardless of which inputs
it's given. The two live hypotheses EXP-012 named (prompt under
-elicitation vs. many claims being genuinely legitimate unquoted
paraphrases) remain undistinguished — this experiment adds evidence the
pattern is real and general, not evidence toward either specific cause.

## What did NOT change

- No fix attempted for the `source_quote` gap this pass — flagged
  clearly (again) as a real, concrete follow-up candidate, not chased
  further here.
- No change to `claim_extraction.py`'s prompt or schema.

## Raw data

`research/results/multimodal_8way_coverage_20260818.json` (full
per-item, per-condition claim detail). Generator:
`backend/research/multimodal_v2/run_8way_coverage.py`.
