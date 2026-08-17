# EVIDENCE_RETRIEVAL_V2_QUERY_TYPE.md — Phase 6

Status: 2026-08-18. `research/RESEARCH_ROADMAP_V2.md` Phase 6: implement
Step 13's 5-query structure (exact_claim/entity_focused/primary_source/
contradiction/context_history), measure each query type's individual
contribution against the documented baseline
(`research/EVIDENCE_EVALUATION.md`: 23.5% source-tier-classification
rate, 68.75% relevant-primary-source rate, 18.75% usable-evidence rate,
n=68 sources / 9 claims).

## What was built

`app/services/ai/prompts.py`'s `RESEARCH_PLANNING_SYSTEM_PROMPT` now
requires exactly 5 typed queries (schema-enforced via a Pydantic
`model_validator` on `ResearchPlan` — `app/schemas/research.py`), one of
each: `exact_claim`, `entity_focused`, `primary_source`, `contradiction`,
`context_history`. New `SearchQuery.query_type` column (migration
`ad9d67b949f7`) traces each fetched `Source` back to the query type that
found it via the already-existing `Source.retrieval_query_id` link — no
new tracing infrastructure needed.

**Real schema-compliance issue found and fixed before any measurement
ran**: llama3.2's first two live attempts included one schema-valid
5-query plan that duplicated `primary_source` and dropped
`context_history` entirely — passes length/enum checks alone, useless
for a clean per-type comparison. The `model_validator` now rejects this
explicitly (a real regression test uses this exact observed case), which
routes through the existing Ollama-retry → Gemini-fallback path every
other stage already has via `get_llm_provider()` — confirmed live: the
very next real attempt against the same claim succeeded on Ollama's own
retry, no new failure-handling code required.

## Real measurement (EXP-015)

4 real DEV-split claims (topically diverse, not all from one cluster),
full real chain (`research_planning.plan_research` →
`search_fetch.fetch_evidence_sources` → `evidence_analysis.
analyze_evidence`), each inside a rolled-back transaction. 20 queries (4
× 5), 42 sources fetched, 16 classified `primary_government`/
`primary_legal`/`primary_data` tier. Every primary-tier source's
title/passage was manually reviewed against its claim (same discipline
as the original "draft human judgment," not a heuristic).

| Metric | Baseline (n=68, 9 claims) | This pass (n=16 primary, 4 claims) |
|---|---|---|
| 1. Source-tier classification rate | 23.5% (16/68) | **38.1%** (16/42) |
| 2. Relevant-primary-source rate | 68.75% (11/16) | **43.75%** (7/16) |
| 3. Primary-source fetch-success rate | 100% (by construction) | 100% (by construction, unchanged) |
| 4. Usable-evidence rate (of primary-tier) | 18.75% (3/16) | **0%** (0/16) |

**This is a real, honest mixed-to-negative result, not the clean
improvement a naive reading of "more structured retrieval" might
predict.** Reported as such, per this program's standing rule that a
negative result gets equal prominence.

## Per-query-type breakdown (this pass's own primary contribution)

| Query type | Primary-tier sources found | Manually judged relevant | Usable (non-irrelevant stance) |
|---|---|---|---|
| exact_claim | 3 | 0 (0%) | 0 |
| entity_focused | 4 | 1 (25%) | 0 |
| primary_source | 4 | 3 (75%) | 0 |
| contradiction | 3 | 1 (33%) | 0 |
| context_history | 2 | 2 (100%, n=2) | 0 |

`primary_source` and `context_history` queries found the most
topically-relevant primary-tier sources; `exact_claim` and
`entity_focused` performed worst. But this ranking is driven almost
entirely by one confound, disclosed rather than smoothed over below.

## The real confound: one claim with no natural primary-source angle

Of the 16 primary-tier sources, **7 came from a single claim**
("Kunwar Vishnu Singh Rajput is an Organization Secretary of Karni
Sena") — a claim about a private political/social organization with no
natural government angle. All 7 were manually judged **not relevant**:
a Gujarat seismology institute's insurance-claims page, an IRDAI
insurance PDF, an Income Tax assessment page, a Karnataka government
directory, a Supreme Court hearing list, and two Punjab legal-services
pages — every one matched only because unrestricted/`site:`-filtered
DuckDuckGo searches for generic keyword combinations ("claims",
"organization", entity names that collide with common government-portal
vocabulary) happened to land on `.gov.in`/`.nic.in` domains, which
`source_scoring.py`'s domain-pattern tier classification then correctly
(by its own narrow rule) tagged `primary_government` -- with zero check
on whether the *content* has anything to do with the claim.

Excluding this one claim's 7 sources, the remaining 3 claims' primary
-tier sources are 7/9 relevant (78%) -- *above* baseline, and much
closer to what a clean per-type comparison would need. **The real
finding is not "the 5-query structure doesn't work" -- it's that the
`primary_source` query type (and, transitively, `exact_claim`/
`entity_focused` searches that incidentally hit government domains) is
actively harmful for claims whose subject has no natural
primary/official source to find, exactly as this experiment's own
design (`primary_source`, "never skipped, even if you expect it to
return little") predicted might happen but did not prevent.**

Usable-evidence rate at 0/16 is a separate, real, more troubling number
that survives even excluding the Karni Sena claim (0/9 for the other 3
claims too) -- consistent with, and an even sharper version of, the
original evaluation's own "single most important finding": most
primary-tier hits are homepages, portals, or generic department pages
too broad for `evidence_analysis` to extract a real stance from, not a
failure to find topically-plausible sources.

## Interpretation and next step (not applied this pass)

Per Phase 6's own failure condition ("if the bottleneck is downstream of
retrieval... report that explicitly rather than attributing the gap to
retrieval by default"): this pass's near-zero usable-evidence rate is
attributable to *both* a real retrieval-relevance gap (the Karni Sena
confound) *and* the same downstream generic-source problem the original
evaluation already diagnosed -- not collapsed into one explanation.

A concrete, scoped candidate fix for the retrieval side, **not
implemented this pass**: make the `primary_source` query type
conditional on whether the claim's extracted entities/topic plausibly
have an institutional/government angle, rather than always firing --
would require a real decision rule (not yet designed) and its own
before/after comparison, consistent with this program's discipline
against changing behavior without a measured reason.

## What did NOT change

- `source_scoring.py`'s tier classification itself (still pure
  domain-pattern matching, no content-relevance check) -- the Karni Sena
  confound is a direct, disclosed symptom of this existing design, not a
  new bug introduced this pass.
- No change to `evidence_analysis.py`'s stance-labeling logic.

## Raw data

`research/results/evidence_retrieval_v2_query_type_contribution_20260818.json`
(full per-claim, per-query, per-source detail, including every
manually-reviewed passage). Generator:
`backend/research/evidence_retrieval_v2/measure_query_type_contribution.py`.
