# Baseline Specification

Every baseline below must use the **same underlying model**
(`llama3.2` via the same local Ollama instance TruthLens itself uses)
and, where the baseline has search access at all, the **same search
provider** (`DuckDuckGoSearchProvider`, `backend/app/services/search/duckduckgo.py`)
that TruthLens itself uses in production (`SEARCH_PROVIDER=duckduckgo`
is the project default — confirmed in `backend/app/core/config.py`).
This holds model quality and search-infrastructure quality constant so
that any measured difference is attributable to *architecture*, per the
brief's explicit warning against a "cheap model vs. expensive model"
confound.

None of baselines 2-4 exist yet as code. This document is their
specification, written during Day 1's planning so they can be built
without ambiguity on Day 3. Baseline 1 already exists.

## Baseline 1 — LLM-only

**Status: already built.** `research_paper/benchmark/run_naive_baseline.py`.
Claim text → `llama3.2` via Ollama, bare prompt asking for a verdict +
reasoning. No claim decomposition (the claim is given, not extracted by
the baseline itself, since this baseline is being compared against
TruthLens's downstream stages, not its claim-extraction stage — see
RQ2's exact framing). No search. No retrieved evidence. No validation.

Existing result on the 2-item Tier-1 set (`benchmark/naive_baseline_results.jsonl`):
both items returned `UNVERIFIABLE` — the model correctly recognized it
had no way to know about mid-2026 events from training data alone,
rather than confabulating an answer. This is real, already-collected
data, reused not re-run, for the Day 8 final table — unless the
held-out dataset (§`DATASET_SPEC.md`) grows beyond these 2 items, in
which case this baseline is re-run against the full set once, at the
same frozen point as every other configuration (Day 8, not before).

**Reuse note**: this baseline's existing framing ("what would a bare
LLM say with zero pipeline") answers a different, narrower question than
baselines 2-3 below ("what would a search-equipped bare LLM say") — the
existing paper draft already flags this precisely ("mostly shows that
search access matters... not the comparison that actually matters
most"). Baselines 2-3 exist specifically to close that gap; baseline 1
is kept as the floor, not discarded.

## Baseline 2 — Search + LLM (single-shot)

**Status: to build, Day 3.**

```
claim_text
  → DuckDuckGoSearchProvider.search(claim_text, max_results=5)
  → top-5 (title, snippet) pairs, NO full-page fetch
  → single LLM call: system prompt = new "baseline_search_llm.v1",
    user content = claim + the 5 (title, snippet) pairs
  → verdict (same VerdictLabel enum TruthLens uses, so results are
    directly comparable)
```

This isolates "has search access at all" from "has TruthLens's specific
multi-stage decomposition/retrieval/validation design" — the exact
comparison the existing paper draft's Discussion section already
identifies as missing (`sec:discussion`, "Baseline comparison is
preliminary and too coarse").

Deliberately **does not** decompose the claim into sub-claims, does not
tier sources, does not run a separate evidence-analysis pass per source,
does not run deterministic validation. One query. One model call.

Query construction: the claim text is passed to search verbatim (no
research-planning LLM stage) — this is the single most important
architectural difference from baseline 3 and from TruthLens itself, and
must not be blurred by "helpfully" improving the query.

## Baseline 3 — Search + RAG + LLM

**Status: to build, Day 3.**

```
claim_text
  → DuckDuckGoSearchProvider.search(claim_text, max_results=5)
  → for each result: fetch + extract full page text (reuse
    search_fetch.py's own fetch/extract path so page-retrieval quality
    is held identical to what TruthLens itself gets — not a weaker
    re-implementation)
  → concatenate up to N characters of each page's text (cap chosen to
    match evidence_analysis.py's own _MAX_PASSAGE_CHARS=8000 per
    source, for comparability)
  → single LLM call over claim + concatenated passages
  → verdict
```

Differs from Baseline 2 only in using full page text instead of search
snippets — isolating "does retrieval depth matter" as its own variable,
separate from "does multi-stage decomposition matter" (tested by the
full system) and "does per-source evidence analysis before verdict
matter" (also only tested by the full system, since baseline 3
concatenates everything into one call rather than analyzing each source
independently the way `evidence_analysis.py` does).

## Baseline 4 — TruthLens minus deterministic validation

**Status: to build, Day 3, small change.**

Implemented as a **runtime flag, not a forked codepath** — this is a
deliberate design choice so this baseline can never silently drift from
the real system as TruthLens itself changes. Concretely: add a
`SKIP_VALIDATION` setting (default `False`, not used in production) that
`verdict.py`'s `propose_verdict()` checks; when `True`, the LLM's raw
`VerdictProposal` is persisted directly (label, confidence,
reasoning_summary, corrected_fact, context_note all taken as-is), and
`validate_verdict()` is still *called* (so its outcome is logged to
`audit_logs` for comparison) but its result is not applied to what gets
published. This is the primary ablation answering RQ1.

## Baseline / System 5 — Full TruthLens

The system exactly as it exists at git tag `truthlens-pre-ieee`. No
baseline-specific code. Every other configuration above is measured
*against* this one changing nothing about it.

## What is held constant across all five

- Model: `llama3.2` via Ollama, same instance, same prompt-formatting
  conventions (structured output schema per configuration, since each
  baseline's task shape differs, but the underlying model call mechanism
  is `OllamaProvider.structured_call`, unmodified).
- Search backend: DuckDuckGo, where the baseline has search access.
- Dataset: the exact same held-out item set, same order, same day's run
  where feasible (see `EXPERIMENT_PLAN.md` §0 on Gemini-quota
  contamination — Gemini is NOT used as the primary model for any
  baseline; only TruthLens's own optional escalation cascade uses it,
  and that escalation rate is itself a measured/reported quantity, not
  hidden).
- Verdict label set: `VerdictLabel` enum (TRUE / MOSTLY_TRUE /
  MISLEADING / MOSTLY_FALSE / FALSE / UNVERIFIED / OUTDATED /
  MISSING_CONTEXT) used for every configuration's output, so accuracy/F1
  are computed on a common label space. A baseline that would naturally
  say "I don't know" in free text is instructed to map that to
  `UNVERIFIED`, not a bespoke label.

## What is NOT held constant, and is the entire point

- Claim decomposition (only the full system and, partially, baseline 4
  do this — baselines 1-3 operate on the claim as already extracted by
  TruthLens's own claim-extraction stage, since evaluating claim
  extraction itself is RQ3/RQ4's job, not RQ2's).
- Source tiering and reliability scoring (only the full system).
- Per-source evidence analysis before verdict (only the full system;
  baselines 2-3 give the model everything at once).
- Deterministic validation (present in baselines 1-3 implicitly — they
  have no such stage to remove — and absent by construction in baseline
  4; present only in the full system).

## Implementation location

```
backend/research/baselines/
    baseline_search_llm.py       # Baseline 2
    baseline_search_rag_llm.py   # Baseline 3
    (Baseline 4 is a config flag in existing verdict.py, not a new file)
    run_baseline.py              # shared CLI: python run_baseline.py --baseline 2 --dataset ../../research/dataset/items.jsonl
```

Each baseline script writes its raw output to
`research/results/baseline_{N}_{timestamp}.jsonl`, one row per dataset
item, schema fixed in `METRICS.md` §"Raw result row schema" so the
Day 10 table-generation scripts can consume any baseline's output
identically.
