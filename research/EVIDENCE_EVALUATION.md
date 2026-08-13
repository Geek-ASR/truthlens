# Evidence Quality Evaluation (Day 6, RQ4)

Status: **real evidence data from Day 5's live pipeline run (68 real
Source/Evidence rows across 9 real verdict-generation events) — one
major bug found and fixed along the way, one metric computed from a
single, unadjudicated draft human review
(`research/evidence_results.csv`), pending Aditya's review.**

## A second major bug found via this data: `explanation` empty in 47% of evidence rows

While reviewing real evidence rows for this evaluation, one row stood
out: a real government source (`newsonair.gov.in`, about Leh/Ladakh
protest restrictions) was classified `stance=contradicts` against an
item-0002 claim, with **zero explanation text** — no way to audit *why*.
Checking systematically: **32 of 68 (47.1%) real evidence rows from
Day 5's run had an empty `explanation`** — the exact "schema-valid but
substantively empty" failure class already fixed twice this session
(`claim_extraction.py`, and flagged for `verdict.py`'s
`reasoning_summary`), but never guarded in `evidence_analysis.py` — a
gap `docs/SYSTEM_AUDIT.md` §5.3 (Day 1) had already named structurally
("this is the one LLM-calling stage with... no substantiveness check")
without yet knowing how large the real impact was.

**Fixed**: `evidence_analysis.py` now has an
`_explanation_looks_substantive()` check, wired into the same
Gemini-escalation pattern the other three LLM-calling stages already
use — but applied **per source**, not per claim, since this stage calls
the LLM once per retrieved source rather than once per claim. New tests
(`test_evidence_analysis_substantive.py`, 4 tests); full suite 150/150
passing.

**Live re-verified against the exact real case that surfaced this**:
re-ran `analyze_evidence()` on the same claim + the same Ladakh source.
Result: same `stance=contradicts`, but now with a real, substantive
explanation: *"The source text describes violent protests in Leh,
Ladakh, and the imposition of restrictions to maintain law and order.
It states that no procession, rally, or march can be carried out
without prior approval from a competent authority, which directly
contradicts the claim that every citizen has the right to express their
views and protest peacefully."*

**Honest nuance, not swept under the rug**: with the explanation now
visible, the `contradicts` stance turns out to be more defensible than
it looked as an unexplained black box — the source's content genuinely
does bear on a broadly-worded claim ("in a democracy, every citizen has
the right to... protest peacefully," with no specific person, place, or
date attached). The real underlying issue this reveals is less "the
evidence-analysis stance was wrong" and more "claim extraction produced
a claim general enough that unrelated-event government sources about
protest restrictions ANYWHERE become plausible 'evidence' for it" — a
claim-specificity problem more than a pure evidence-relevance one. Both
observations are reported; neither is picked over the other because it
tells a cleaner story.

## Real tier / stance / diversity distribution (n=68 sources, 9 claims)

| Source tier | Count | % |
|---|---|---|
| other | 43 | 63.2% |
| primary_government | 14 | 20.6% |
| established_news | 6 | 8.8% |
| primary_legal | 2 | 2.9% |
| news_wire | 2 | 2.9% |
| factcheck_org | 1 | 1.5% |
| primary_data | 0 | 0% |

**Source-tier classification rate (primary_government + primary_legal +
primary_data)**: 16/68 = **23.5%** (Wilson 95% CI: 15.0%–34.9%) — a
different, real number from the paper's existing "95%" figure
(`main.tex` §V-F), because that figure measured `tier1_primary`
-restricted queries specifically; this run used the system's normal,
unrestricted research-planning queries for these particular claims. Not
a contradiction — a different experimental condition, stated as such.

| Evidence stance | Count | % |
|---|---|---|
| irrelevant | 58 | 85.3% |
| contradicts | 8 | 11.8% |
| supports | 2 | 2.9% |
| provides_context | 0 | 0% |

**Evidence signal-to-noise: 85.3% of retrieved-and-analyzed sources were
judged irrelevant** — notably higher than the existing paper's
previously-reported 55.6% (`main.tex`, "Evidence signal-to-noise"
subsection), on a different, smaller, real sample. Both numbers are real
and should both be reported, not averaged into one, since the paper
should be honest that this ratio moves around across samples rather than
implying a single stable rate.

**Source diversity**: 29 distinct domains across 68 sources (many
claims' searches converged on the same small set of NEET/medical
-admission-authority domains, which is topically appropriate for
item-0001's cluster of related claims, not a diversity failure).

## The four-way primary-source metric (`METRICS.md` §4), not collapsed into one number

Per the explicit instruction not to report a single primary-source
percentage without its denominator:

1. **Source-tier classification rate**: 16/68 = 23.5% (above).
2. **Relevant primary source rate** (draft human judgment,
   `research/evidence_results.csv`): of the 16 primary-tier sources,
   **11/16 (68.75%)** are judged topically relevant to the claim's
   general subject — a real government/legal source on the right
   general topic, even when too generic to confirm the specific atomic
   fact. The 5 judged not relevant include one genuinely wrong-domain
   case (`josaa.nic.in`, the ENGINEERING admissions authority, returned
   for a MEDICAL/NEET claim) and one wrong-country case (the US
   National Archives' copy of the US Constitution, returned for an
   Indian political claim) — both real, concrete instances of exactly
   the kind of false-positive-relevance risk already flagged in
   `main.tex` §V-F's "Karni Sena" finding, now with two more examples.
3. **Primary source fetch-success rate**: not independently re-measured
   in this pass (all 16 primary-tier rows exist in the `Source` table
   at all only because `search_fetch.py` already guarantees it never
   stores a source it couldn't fetch — see `docs/SYSTEM_AUDIT.md` — so
   this is 16/16 by construction of that existing guarantee, not a new
   measurement; whether the *full* text vs. a snippet-only fallback was
   retrieved for each was not checked here and is a real gap, same as
   the `.gov.in` fetch-reliability caveat already in `main.tex` §VII).
4. **Usable evidence extraction rate** (system's own stance output,
   `stance != irrelevant`): 3/16 = **18.75%**.

**The gap between metric 2 (68.75%) and metric 4 (18.75%) is the single
most important finding of this evaluation.** The system's retrieval is
finding real, topically-appropriate, legitimate primary-government/legal
sources at a meaningfully higher rate (68.75%) than its own "usable
evidence" number (18.75%) would suggest — the bottleneck is that most of
these real sources are homepages, portals, or generically-relevant
documents too broad to confirm or deny one *specific* atomic fact (an
exact score, an exact date), not a failure to find relevant sources in
the first place. A reader who only saw metric 4 would conclude retrieval
quality is poor; metric 2 shows the more accurate, more nuanced picture.
Reporting only one of these two numbers would misrepresent the system in
either an unfairly harsh or unfairly flattering direction — both are
published together for exactly this reason.

## Citation Correctness (spot-checked via Day 5's validator audit, not independently re-sampled here)

`research/VALIDATOR_EVALUATION.md`'s draft human review already
examined citation correctness as part of its TP/FP/TN/FN judgments (the
"paan shop owner" case is a real citation-correctness failure: a citation
to a real, fetched, on-topic-sounding article about a *different*
specific person). Not re-duplicated here as a separate count to avoid
double-reporting the same underlying finding under two different metric
names.

## What's next

1. Human review/adjudication of `evidence_results.csv`'s
   `draft_human_topical_relevance` column.
2. `.gov.in`/primary-source fetch-completeness (metric 3 above) is a
   real, still-open gap first found in the earlier primary-source-fix
   work (`main.tex` §VII) and not newly measured here — a candidate for
   a dedicated Day 8+ pass rather than left implicitly "done" by
   omission.
3. The `josaa.nic.in`/wrong-domain and `archives.gov`/wrong-country
   cases are concrete instances worth a taxonomy entry alongside the
   existing "Karni Sena" false-positive-relevance finding — domain
   -restricted search guarantees tier correctness, not topical or
   geographic relevance, now demonstrated three separate times.
