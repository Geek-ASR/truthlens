# TruthLens System Audit — Day 1 of the IEEE Experimental Program

Date: 2026-08-13. Frozen at git tag `truthlens-pre-ieee` (HEAD `fdc31dc`).
Everything in this document was verified by reading the actual current
code and running the actual current test suite on this date — nothing
here is carried over from memory of earlier sessions without
re-checking it against the files as they exist right now.

## 1. Purpose

This is the Day 1 deliverable of the 10-day IEEE-submission program:
understand exactly what exists, freeze it, and identify every place
results could be silently lost, fabricated, or miscounted before any
experiment is designed on top of it. It is a companion to
`docs/CURRENT_ARCHITECTURE.md` (the general living architecture doc,
updated alongside this file) — this document is specifically the
fabrication/reproducibility risk inventory for the experimental program,
not a general feature description.

## 2. Reproducibility check (Day 1, task 8)

```
cd backend && .venv/bin/python3 -m pytest tests/ -q
```
Result at freeze: **142 passed, 0 failed, 4 deprecation warnings (unrelated
— `datetime.utcnow()` in `jose`/`botocore` dependencies, not project code)**.
26 test files. This is the reproducible baseline every later experiment
result must be comparable against; if this number changes on a later
`git checkout truthlens-pre-ieee`, the environment has drifted, not the
code.

No live pipeline run (real reel → real fact-check) was re-executed as
part of this specific audit pass, to avoid spending today's Gemini
free-tier quota (20 requests/day, already established this project runs
against a hard external limit — see §5). The most recent real end-to-end
verification is documented in `research_paper/main.tex` §V and the
`research_paper/benchmark/` artifacts, both from the days immediately
preceding this freeze.

## 3. Complete pipeline stage inventory (`backend/app/pipeline/`)

Verified by reading every file listed, not by grep summary:

| Stage file | Role | LLM call? | Deterministic guard present? |
|---|---|---|---|
| `ingestion.py` | Extract audio/frames (video) or single frame (photo) from fetched media | No | — |
| `transcription.py` | Whisper transcript (local `faster-whisper` or OpenAI API) | No (ASR, not LLM) | — |
| `ocr.py` | Tesseract OCR over sampled frames | No | — |
| `vision_context.py` | Scene description + on-screen-text read via vision LLM | Yes (`llava-phi3` default) | No substantiveness check on this stage's own output — see §5.4 |
| `claim_extraction.py` | Decompose reel content into atomic claims | Yes | Grounding check (`_extraction_looks_grounded`) + substantiveness check (`_extraction_looks_substantive`, added 2026-08-13) + persist-time empty-text filter |
| `research_planning.py` | Claim → 2-5 search queries with target tier | Yes | None — queries are trusted as generated |
| `search_fetch.py` | Execute queries, archive fetched pages as `Source` rows | No | Never stores a `Source` with empty fetched content; domain-restricted `include_domains` for `tier1_primary`/`tier3_factcheck` queries |
| `source_scoring.py` | Deterministic 8-dimension reliability score | No | Fully deterministic formula; only `directness`/`corroboration` are informed by the (separately validated) evidence-analysis stance |
| `evidence_analysis.py` | Per-source stance (supports/contradicts/context/irrelevant) toward the claim | Yes | None on the stance judgment itself — see §5.2 for a **real, previously-undocumented issue found in this audit** |
| `verdict.py` | Claim-level verdict from the evidence matrix | Yes | None inline — validation happens in the next stage |
| `validation.py` | **The deterministic gate.** 3 checks: citation existence, source-fetch existence, numeric grounding | No (pure Python, regex + set membership) | This IS the guard |
| `overall_verdict.py` | Reel-level verdict from already-validated claim verdicts | No | Fixed rule table, fully deterministic |
| `duplicate_detection.py` | Content-hash + fuzzy claim-text duplicate check | No | `difflib.SequenceMatcher`, threshold 0.85 |
| `reel_content.py` | Assemble carousel content from validated claim/verdict/source rows | Yes (headline, why-paragraph) | Headline number-grounding check; `_safe_supplementary_text` refuses to reuse any non-`passed` verdict's free text |
| `slide_generation.py` / `templates/` | Render PNGs from assembled content | No | — |
| `publishing.py` | Meta Graph API publishing state machine | No | — |
| `audit.py` | Writes `audit_logs` rows for every stage above | No | This is the traceability backbone every later "where did this number come from" question resolves against |

**Orchestration** (`orchestrator.py`, verified in full): `analyze_reel()`
runs transcript→OCR→vision→claims→(per verifiable claim)
research→evidence→verdict, in one un-chunked loop with no per-claim
commit boundary — confirmed live on 2026-08-12/13 that an unhandled
exception partway through this loop (the Gemini 429 bug, now fixed)
discards *all* claims' verdict work for that call, not just the failing
claim's. This is a real architectural fact worth stating plainly in the
paper's threats-to-validity section, not just in a bug-fix commit
message: **the pipeline's unit of atomicity for verdict work is the
whole reel, not the individual claim.**

## 4. Complete prompt inventory (`backend/app/services/ai/prompts.py`, 201 lines, read in full)

Nine versioned system prompts: `claim_extraction.v2`,
`research_planning.v1`, `evidence_analysis.v1`, `verdict.v2`,
`content_generation.v1`, `headline.v1`, `overall_why.v1`,
`vision_context.v1`, plus the shared `NEUTRALITY_CLAUSE` string appended
to seven of the eight (content_generation's is the one exception — it
has no neutrality clause, since it only renders already-validated
content and doesn't make a judgment call). Every prompt that receives
reel-derived text wraps it in a `<<<REEL_DATA_START>>>`/`END` delimiter
with an explicit "this is data, not instructions" framing — the
prompt-injection backstop.

**Audit finding relevant to RQ5 (political bias):** `NEUTRALITY_CLAUSE`
is the *entire* neutrality mechanism. It is a instruction string, not a
measured property. Every prompt that carries it literally asserts
neutrality to the model; nothing in the codebase measures whether the
model actually behaves that way. This confirms the plan's Rule 9 is not
a hypothetical concern — it is the exact current state.

## 5. Fabrication / data-loss / silent-failure risk inventory (Day 1, task 10)

This is the core Day 1 deliverable. Each item below is either (a) a
guard that already exists and should be *tested against*, not
re-invented, or (b) a real gap found during this specific audit pass
that the experimental design must account for.

### 5.1 Guards that already exist (verified by reading `validation.py` in full)
- **Citation existence**: `cited_evidence_ids` must be a non-empty
  subset of the claim's actual evidence IDs, or the verdict is
  downgraded to `UNVERIFIED` with `validation_status =
  downgraded_missing_citation`.
- **Source-fetch existence**: every cited evidence's source must have a
  real `retrieved_at` and `full_text_storage_key` — a source that was
  never actually fetched cannot be cited, downgrade reason
  `downgraded_unfetched_source`.
- **Numeric grounding**: every number (≥2 digits) in `reasoning_summary`
  must appear in the *combined `relevant_passage` text of the cited
  sources* — not the full fetched text, see §5.2 — or the verdict
  downgrades to `downgraded_unsupported_stat`.
- **`corrected_fact`/`context_note` grounding**: independently checked
  against *all* sources' passages (not just cited ones), with no
  digit-count floor (a single-digit fabrication would pass the main
  numeric check's ≥2-digit floor but not this one). Dropped silently
  (not downgraded) if ungrounded. Unconditionally dropped for `TRUE`
  verdicts.
- **Claim-extraction substantiveness** (added 2026-08-13, commit
  `dbd04ae`): an extraction where every returned claim has empty `text`
  triggers escalation; a claim with empty `text` is never persisted
  regardless of escalation outcome.
- **Content-generation completeness**: `content_generation.py`'s
  `_content_looks_complete` requires six specific fields non-empty.
- **Verdict-reasoning substantiveness**: `verdict.py`'s
  `_reasoning_looks_substantive` requires ≥6 real words after stripping
  internal citation markup.
- **Never store an empty source**: `search_fetch.py` never creates a
  `Source` row when both `full_content` and `snippet` are empty.
- **Never persist a downgraded verdict's free text downstream**:
  `reel_content.py`'s `_safe_supplementary_text` returns `None` for any
  verdict whose `validation_status != passed`.

### 5.2 Real gap found during this audit: `relevant_passage` is silently overwritten after evidence analysis, and this can invalidate grounding checks against text that was genuinely fetched

`search_fetch.py` sets `Source.relevant_passage = (snippet or
full_text)[:2000]` at fetch time. Then `evidence_analysis.py` line 78
**overwrites** it: `source.relevant_passage = passage[:2000]` where
`passage = full_text[:8000]` — i.e., after evidence analysis, this field
unconditionally becomes "the first 2000 characters of the first 8000
characters of the full fetched text," discarding whatever the original
search-time snippet was. The comment above that line claims the field is
"refined to the excerpt actually cited, when the model's explanation
quotes/paraphrases a shorter section" — **this is not what the code
does.** The model's `explanation` field is never consulted when setting
`relevant_passage`; it is a fixed positional truncation.

**Why this matters for the experimental program**: `validation.py`'s
numeric-grounding check (§5.1) checks a cited number against
`cited_sources`' `relevant_passage` — i.e., against this post-overwrite,
first-2000-characters-of-8000 value, not the full fetched text and not
specifically what the model actually cited. A real, correctly-cited
number that happens to appear between character 2000 and the end of a
long article would now cause a **false downgrade** — the validator would
report "unsupported," but the number genuinely was in the fetched,
retrievable source text; it was just truncated out of the field the
validator happens to check. This is a real, previously undocumented
methodological risk to the "28.6% of verdicts downgraded" telemetry
already in the paper: some unknown fraction of that 28.6% could be this
truncation artifact rather than a genuine hallucination. **This must be
measured, not assumed**, during Day 5's validator audit (human
reviewers should check, for each `downgraded_unsupported_stat` case,
whether the missing number appears anywhere in the source's *full* text,
not just in `relevant_passage`).

### 5.3 Real gap: evidence-analysis stance judgment has no deterministic check at all

Every other LLM-generation stage in the pipeline has *some* deterministic
guard (§5.1). `evidence_analysis.py`'s stance classification
(supports/contradicts/provides_context/irrelevant) has none — its output
is trusted directly into `Evidence.stance`, which then feeds
`source_scoring.update_after_evidence`'s corroboration/directness
refinement and, downstream, the verdict LLM's evidence matrix. A source
whose stance is misjudged (the entity-confusion case already documented
in the paper's taxonomy — Sri Ram Sena evidence judged `contradicts` a
Karni Sena claim) propagates through corroboration scoring and into the
verdict prompt with no gate at all. **This is a legitimate target for
Day 5/6's evidence-quality evaluation**: humans should independently
label stance for a sample of (claim, source) pairs and compute
agreement/error rate against the LLM's stance, the same way Day 5 does
for the verdict validator.

### 5.4 Real gap: vision-context stage has no substantiveness or grounding check

`vision_context.py` is the one LLM-calling stage with zero deterministic
guard of any kind — not grounding, not substantiveness, not even the
"is this empty" check that content_generation and claim_extraction have.
The live-found "garbled meta-commentary" scene-description failure
documented in the paper's taxonomy (`llava-phi3` outputting prompt-echo
nonsense instead of a real description) went completely undetected by
any code check; it was only found by a human reading a database row.
Since `scene_description` is explicitly "advisory only, never cited as
evidence" per its own prompt, this is lower-severity than §5.2/5.3 — but
`visible_text_or_graphics` (which IS used as claim-extraction input,
weighted equally with OCR) has the same zero-guard status and is higher
severity. **Candidate for a Day 5-adjacent fix**: at minimum, log/flag
when vision output looks like the same degenerate-repetition pattern
already observed twice live (Aug 12 and Aug 13 runs both produced
scene_description text resembling re-echoed prompt fragments rather than
image description) — this is now a *repeated*, not one-off, failure
mode and should be named as such in the paper rather than treated as an
isolated anecdote.

### 5.5 Real constraint: Gemini escalation is not just a quality mechanism, it is a shared, rate-limited resource across dev and eval

`GEMINI_API_KEY`'s free tier is capped at 20 requests/day (confirmed
live 2026-08-12/13 by exhausting it). Every pipeline stage that
escalates (`claim_extraction`, `evidence_analysis` — no, evidence
analysis does not escalate, only claim_extraction, content_generation,
and verdict do, per direct code inspection of the three
`if settings.LLM_PROVIDER == "ollama" and settings.GEMINI_API_KEY`
blocks) draws from the *same* daily quota used for whatever manual
testing happens the same day. **This is a direct threat to the planned
baseline/ablation experiments**: if baselines 2-4 (§ see
`BASELINE_SPEC.md`) also use Gemini as an escalation/comparison model,
running them on the same day as system development will contaminate
both the day's remaining quota and, if not careful, the escalation rate
telemetry itself. The experiment plan must either (a) run all
quota-sensitive experiments on isolated days with no concurrent
development use, or (b) use a paid tier for the evaluation window, or
(c) design baselines/ablations to run entirely on Ollama with Gemini
usage measured but not required for a valid result. Recommendation is
(c), documented in `EXPERIMENT_PLAN.md`.

### 5.6 Real constraint: `RESEARCH_FAILED` vs `UNVERIFIED` is implemented correctly, but only at the claim level, not surfaced as a distinct dataset-item outcome

Per Rule 7, these must never be conflated. Confirmed by code
(`orchestrator.py` line 66-76, `overall_verdict.py` line 27-37): a claim
whose every search query errored gets `ClaimStatus.research_failed` and
**no Verdict row at all**; `build_reel_fact_check` refuses to build a
fact-check if *every* verifiable claim is in this state. This is
correctly implemented. **What's missing for the experimental program**:
when running the held-out dataset through the system, an item that hits
`RESEARCH_FAILED` must be recorded and reported as an infrastructure
failure in the results tables — not silently excluded (which would
inflate accuracy by dropping hard cases) and not counted as a wrong
verdict (which would be equally misleading). `METRICS.md` defines this
explicitly.

### 5.7 What is NOT a fabrication risk (checked and ruled out)
- `overall_verdict.py` aggregation: fully deterministic rule table, no
  LLM involvement, directly auditable. No further evaluation needed
  beyond confirming the rule table itself is sound (it already is,
  by inspection — see the note added to `docs/CURRENT_ARCHITECTURE.md`).
- `duplicate_detection.py`: deterministic, `difflib`-based, no LLM.
- `source_scoring.py`'s 8-dimension score: deterministic formula; only
  two of eight dimensions (`directness`, `corroboration`) are informed
  by an LLM judgment (evidence-analysis stance), and that dependency is
  the §5.3 gap already flagged, not a separate one.

## 6. Test coverage gap relevant to the experimental program

`tests/test_validation.py` has 13 tests, all synthetic unit tests of
`validate_verdict()`'s logic in isolation (real inputs constructed by
hand, not real pipeline output). This proves the function does what its
code says; it does **not** establish that a `downgraded_*` outcome
corresponds to an actual hallucination, or that a `passed` outcome
corresponds to an actually-correct, actually-supported claim. That
question — Validator Precision/Recall/F1 against human judgment — has
never been measured and is exactly Day 5's job. Unit tests and a
human-audited validator evaluation are answering different questions;
neither substitutes for the other.

## 7. Freeze confirmation

```
git tag -a truthlens-pre-ieee -m "..."   # done, HEAD fdc31dc
git tag -n99 truthlens-pre-ieee
```
No source files were modified as part of this audit. The only
repository changes on 2026-08-13 up to this point are the two new
documentation files this Day 1 pass produces
(`docs/SYSTEM_AUDIT.md`, an update to `docs/CURRENT_ARCHITECTURE.md`)
and the `research/` planning documents — no pipeline code changed.
