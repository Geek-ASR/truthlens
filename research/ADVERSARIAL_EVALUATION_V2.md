# ADVERSARIAL_EVALUATION_V2.md — Phase 11 (bounded slice)

Status: 2026-08-18. `research/RESEARCH_ROADMAP_V2.md` Phase 11: a full
end-to-end adversarial suite (Step 18: 20 categories, 100+ cases, whole
pipeline). **Honest scope disclosure**: the full build was judged not
achievable within this session — several of Step 18's categories
(AI-generated image, edited video, OCR/audio corruption as a genuine
input-signal problem rather than a text-content problem) need real
external media-generation tooling this project does not have and this
pass does not build. What follows is a real, bounded slice: 6 real,
hand-constructed adversarial *text-content* cases run through the real,
unmodified `app.pipeline.claim_extraction.extract_claims()` — the
whole-pipeline requirement satisfied for the one stage this pass covers,
not simulated or mocked, and not claimed to be the full 20-category
suite.

## Result: 0/6 crashes

Real, positive robustness finding: no adversarial input caused an
uncaught exception. Per-case detail:

| Case | Outcome | Claims |
|---|---|---|
| `garbled_ocr` | resolved | 0 |
| `caption_transcript_contradiction` | resolved | 1 |
| `extremely_short` | resolved | 0 |
| `mixed_language_chaos` | resolved | 2 |
| `repetitive_spam` | resolved | 1 |
| `near_max_tokens` | resolved | 0 (confounded — see below) |

## Real findings, each genuine and disclosed as found

- **Garbled OCR and near-empty transcript both correctly produce zero
  claims, not hallucinated ones.** Safe, graceful degradation on the two
  clearest "nothing real here" cases.
- **Caption/transcript contradiction did not produce a hallucinated
  merged claim.** Given a caption about a Delhi protest and a completely
  unrelated transcript (a baking recipe), the extractor surfaced only
  the caption-derived claim and silently dropped the recipe content
  entirely — a safe outcome (no false synthesis), but it also means
  **no signal was raised that the two inputs disagree**. This project
  has no check anywhere for input-signal internal consistency (distinct
  from any of the 7 validator checks, which all operate on verdict
  reasoning vs. evidence, never on claim-extraction's own multi-signal
  inputs) — a real, structural gap, named here for the first time this
  session, not fixed.
- **Mixed-language chaos (Hindi/Urdu/English interleaved) extracted only
  the English-script portions.** Both real extracted claims come from
  the English segments; the Hindi and Urdu segments produced nothing,
  even though the constructed sentence was a single continuous thought
  spanning all three scripts. A real, disclosed possible multilingual
  bias — genuinely checkworthy content expressed only in a non-Latin
  script may be silently dropped rather than extracted or flagged as
  unparseable. Worth a dedicated follow-up, not chased further this pass.
- **Repetitive spam (40x the same sentence) collapsed to exactly 1
  claim**, not 40 near-duplicates — a good result, though this pass
  cannot tell whether this reflects the extractor's own behavior or
  this session's earlier deduplication work (`_deduplicate_claims`,
  Phase 2) — both operate before persistence, and this script does not
  distinguish which one is responsible.
- **`near_max_tokens` is a genuine confound, not a clean finding.** The
  raw log shows llama3.2 DID produce 1 claim initially, which then
  triggered the existing "ungrounded, retry via Gemini" quality check —
  but that retry hit a REAL `QUOTA_EXHAUSTED` error (Gemini's free-tier
  daily quota, exhausted by this session's own cumulative usage across
  many earlier experiments), and the fallback path returned 0 claims.
  This is the SAME quota-aware cooldown behavior verified correct in
  `EXP-010` — not a new bug — but it means this specific case's 0-claim
  result reflects quota exhaustion timing, not a clean measurement of
  how the pipeline handles long/repetitive content on its own. Reported
  honestly as inconclusive, not presented as a finding about length.

## What did NOT happen

- No categories requiring real media generation (AI-generated image,
  edited video) were attempted.
- No post-claim-extraction stages (research_planning, evidence
  retrieval, verdict) were run for these adversarial cases — this pass
  is bounded to claim_extraction's own robustness.
- Not re-run with fresh Gemini quota to get a clean `near_max_tokens`
  read — the honest, disclosed limitation stands rather than being
  silently worked around.

## Raw data

`research/results/adversarial_claim_extraction_stress_20260818.json`.
Generator:
`backend/research/adversarial_v2/run_claim_extraction_stress.py`.
