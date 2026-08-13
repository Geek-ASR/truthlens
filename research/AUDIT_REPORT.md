# AUDIT_REPORT.md — Phase 0 Full Research Audit

Status: 2026-08-13. Read-only audit against the repository and
`research_paper/main.pdf` as of commit `8b76765`. **No paper or system
changes were made while producing this document**, per the governing
instruction to complete Phase 0 before touching anything. Every claim
below is either verified directly against raw code/data in this pass
(marked **[verified this pass]**) or carried forward from this project's
existing, already-disclosed documentation (marked **[prior finding]**).
Two new, previously-undisclosed issues were found — they are the most
important content in this document and are surfaced first, not buried.

---

## Top findings (read this section first)

### Finding 1 (CRITICAL): Baselines 1–3 never received TruthLens's own extracted claims — they received the dataset's hand-written claim text, for every item, for the entire program

**[verified this pass, via source + raw output inspection]**

`BASELINE_SPEC.md` states explicitly, twice, that baselines 1–3 are
designed to operate "on the claim as already extracted by TruthLens's
own claim-extraction stage" — the whole point being to isolate
downstream architecture from claim-extraction quality (RQ2 vs. RQ3/RQ4).

The actual code does not do this. `backend/research/baselines/common.py`,
`make_result_row()`:
```python
"claim_ids_extracted": [],  # baselines 2/3 don't do claim extraction; see BASELINE_SPEC.md
"claim_texts_extracted": [item.get("claim_text", "")],
```
`item["claim_text"]` is `research/dataset/items.jsonl`'s own field — a
clean, human-written summary of the claim, authored during dataset
construction by reading the professional fact-check article (e.g.
item-0001: *"Video captures NEET 2026 candidates sharing their joy after
the results were declared on July 16, 2026."*). Every one of
`baseline_llm_only.py`, `baseline_search_llm.py`, and
`baseline_search_rag_llm.py` calls `run_item(item["claim_text"], ...)`
directly. `common.py` was written once, Day 3 (`aa656bb`), and has never
been modified since — this has been true of **every baseline run in this
entire program**, including the frozen Day 8 run behind the paper's
headline finding.

**Why this matters**: TruthLens's own claim extraction is extensively
documented in this project as noisy — empty-string claims, near-duplicate
OCR-frame variants, zero-verifiable-claims outcomes on two of the six
headline-comparison items. Baselines never had to survive any of that;
they were handed a clean, professionally-worded claim statement every
time. The paper's headline finding ("Search+LLM beats full TruthLens on
the paired 6-item set") and its explanation ("traces to claim-extraction
coverage failures... not a mysterious general weakness") are *directionally
consistent with this bug*, but the bug means the comparison was never
actually isolating "architecture" the way the paper's methodology section
claims to. A skeptical reviewer would correctly identify this as
invalidating the "conditional on the same extracted claim inputs" framing
Phase 12 of your brief specifically asks me to verify — that framing is
not currently true.

**Scope**: affects Table I, Table II (main results), the McNemar test,
and by extension the entire RQ2 narrative and the paper's Discussion
section's reading of DeVerna et al. It does **not** affect the validator
audit (Section IX, which runs the real production pipeline including real
claim extraction) or the multimodal claim-coverage experiment (Section X,
which also runs real extraction).

**Not fixed in this document** — per Rule 2, fixing this means re-running
baselines against TruthLens's *actual* extracted claims (a new, real
experiment with real LLM calls), not silently editing existing output
files. Recommended as the first item in Phase 1/O below.

### Finding 2: The live database mixes development-era and held-out-benchmark data with no separation flag, and no longer matches the paper's published evidence-quality snapshot

**[verified this pass, via live query]**

Postgres is live on this machine (`pg_isready` succeeds; not previously
known to be running — `REPRODUCIBILITY.md` had disclosed this as
unavailable). Querying it directly:

| Table | Live row count |
|---|---|
| `reels` | 20 |
| `claims` | 62 |
| `evidence` | 207 |
| `sources` | 223 |
| `verdicts` | 38 |

`reels` includes a literal `https://example-test.local/reel/synthetic-test-1`
row (Phase-4-era synthetic test data, pre-dating this research program
entirely) alongside real dataset items, **and several dataset URLs are
ingested 2–3 times each** (e.g. `DbuqfKHN1zI` three times,
`Dbrw0EPhFcU` and `Db6Dd14Cte5` and `Dbns78RDIXY` twice each) — different
`reels.id` UUIDs for the same underlying post, from different pipeline
runs across different days. No column on `reels` marks "this row is part
of the frozen 9-item benchmark" vs. "this row is leftover
development/test data" vs. "this row is a superseded re-ingestion of a
benchmark item." Live evidence-stance counts (152 irrelevant / 30
supports / 25 contradicts, $n=207$) bear no resemblance to
`EVIDENCE_EVALUATION.md`'s published $n=68$ (58/2/8) — confirming that
figure was a snapshot at one point in time, not a live-reproducible query,
exactly as `REPRODUCIBILITY.md` already (partially) disclosed, but the
scale of drift (207 vs. 68 — three times more data now) was not
previously known or stated.

**Why this matters**: any attempt to "just query the database" to
regenerate or extend the evidence-quality numbers (as Day 10's
`REPRODUCIBILITY.md` suggested as a future fix) would silently mix
benchmark and non-benchmark data unless every query is scoped by an
explicit, maintained list of the correct `reels.id` values for the frozen
9-item run — which does not currently exist as a committed artifact
anywhere in the repository.

---

## A. Current architecture

9-stage pipeline (ingestion → claim extraction → research planning →
search/fetch → evidence analysis → verdict proposal → 4-check
deterministic validation → rule-based aggregation → content assembly),
FastAPI/Postgres+pgvector/MinIO backend, Ollama-first with Gemini
escalation gated by per-stage substantiveness checks. Source scoring:
8-dimension weighted rubric, **[verified this pass]** weights hand-set in
`backend/app/pipeline/source_scoring.py` (`primary_source_status` 0.20,
`author_identity` 0.05, `publication_reputation` 0.20,
`evidence_transparency` 0.10, `recency` 0.10, `directness` 0.15,
`corroboration` 0.15, `conflict_of_interest` 0.05 — sums to 1.00). No
evidence in code comments, commit history, or docs that these weights
were tuned against any evaluation data — they read as reasonable manual
priors, not a fit result. This should be stated plainly as "hand-set, not
tuned or validated" rather than implied to be empirically derived
(Phase 7).

## B. Current dataset

9 items, all Tier 1, `research/dataset/items.jsonl`. **[verified this
pass, direct file read]**: 7 FALSE / 1 TRUE / 1 MISLEADING ground truth;
5 `provenance`-type claims; actors BJP×3, six other actors ×1 each;
item-0003 permanently unfetchable (3 attempts). Sourced at a measured
~8% Tier-1 hit rate. Single annotator (this project) for any Tier-2-style
judgment; zero Tier-2 items in the frozen set; no IAA computed or claimed.

## C. Current experiments

Baselines 1–4 + full system (Finding 1 above applies to 1–3). Claim
-decomposition ablation, $n=4$ — **[verified this pass]** no generator
script exists for `research/results/claim_decomposition_ablation.json`;
it is a hand-constructed reanalysis of already-collected per-claim
verdict data, not a freshly-run paired experiment. This is *methodologically
legitimate* (each claim's verdict is independently computed research
-then-reasoning regardless of how many total claims were extracted in
that run, so reusing the real per-claim verdict to ask "what would
aggregation of only claim 1, vs. all claims, produce" is a valid
counterfactual) but it does **not** test whether the *decision* to
decompose changes upstream search/evidence behavior for the primary
claim itself — only whether aggregating already-researched additional
claims changes the final label. Phase 8's suggested reframing
("counterfactual claim-selection analysis" rather than "ablation") is
more accurate than the paper's current description and should be
adopted. Multimodal claim-coverage ($n=6$/7, Day 4, real ingestion + 3
real modality conditions, single non-repeated call per condition).
Validator audit ($n=9$, real pipeline, single-reviewer draft judgment,
before/after two general fixes). Evidence-quality audit ($n=68$
snapshot — see Finding 2). Source-tier domain-restriction fix (real,
$n=20$, a *different, smaller* sample than the $n=68$ evidence-quality
run — already correctly disclosed as a separate experimental condition in
the paper, confirmed accurate on re-read).

## D–E. Current claims made in the paper, and their supporting evidence

| Claim | File/artifact | Confidence after this audit |
|---|---|---|
| Headline: TruthLens 33.3% vs. B2 66.7%, paired $n=6$ | `day8_summary.json`, regenerated and verified Day 10 | **Numerically correct, but the comparison's validity claim ("conditional on same claim input") is false — Finding 1** |
| Decomposition: 50.0% vs. 25.0%, $n=4$ | `claim_decomposition_ablation.json` | Numerically correct; description should change from "ablation" to "counterfactual claim-selection analysis" |
| Validator recall 16.7%→40%, $n=9$ | `VALIDATOR_EVALUATION.md` + addendum | Correct and already fully disclosed, including its own calibration-circularity caveat |
| Four-way evidence metric, $n=68$/16 | `EVIDENCE_EVALUATION.md` | Correct *as a historical snapshot*; not currently reproducible from the live DB without a scoping artifact that doesn't yet exist (Finding 2) |
| Source-tier fix 11%→95%, $n=20$ | `main.tex` §"Closing the primary-source gap" | Correct, distinct sample, already disclosed as such |
| Structural cross-post finding, 4/6 items | `MULTIMODAL_EVALUATION.md` | Correct on re-read of the underlying per-item notes |

## F. Evidence missing for each claim

- No independently-run version of the headline comparison exists using
  TruthLens's actual extracted claims for baselines (Finding 1).
- No true paired single-vs-multi-claim pipeline run exists (C, above).
- No re-derivation of the $n=68$ evidence-quality figures against current
  data exists, and no committed query/script exists to produce one
  correctly scoped to only the 9 benchmark items (Finding 2).
- No entity-consistency validator exists yet in any form (Phase 5 asks
  for one; confirmed absent from `backend/app/pipeline/validation.py`).
- No validator dev/test split or synthetic adversarial benchmark exists
  (Phase 4); the only validator evaluation is the $n=9$ real-case audit,
  which is also the same data the new Check 4 was calibrated against
  (already disclosed as circular in the paper itself).

## G. Potential data leakage

Two forms, both already partially disclosed but worth stating together
here: (1) Check 4's phrase list and the vision-context prompt-echo
threshold were both calibrated by reading real failure cases from the
frozen dataset's own audit output — general principles, specific
calibration, disclosed in `main.tex` §IX as a named threat to validity.
(2) **[new observation this pass]** The same person (Aditya, assisted by
this agent) both selected which 9 items to include in the benchmark *and*
wrote each item's `claim_text` summary *and* built/evaluated the system
being tested. Tier-1 verdicts are genuinely independent (professional
orgs' own published labels), but the *claim framing* baselines are scored
against — which, per Finding 1, is what baselines actually see — was
written by the system's own author with full knowledge of the fact
-check's conclusion. This is a much softer concern than classic leakage
(the label itself is external) but is worth naming: a claim summary
written by someone who has already read the verdict may be phrased in a
way that's easier to correctly classify than an extraction pipeline
encountering the same content cold.

## H. Potential test-set contamination

No prompt, threshold, or model choice was changed based on dataset item
*content* after the freeze tags, as far as git history shows — the two
post-freeze fixes are ground-truth-independent pure functions of model
output (already disclosed). The more relevant contamination risk found
this pass is Finding 1 (baselines never faced the same "cold" extraction
problem TruthLens does) and G above.

## I. Numerical inconsistencies

Three found and fixed across Days 9–10 (6-vs-7 FALSE miscount;
`day8_final_tables.py` variable-shadowing bug; figure-numbering mismatch
in `REPRODUCIBILITY.md`) — all already corrected and documented in prior
commits. **New this pass**: the $n=68$ vs. live $n=207$ evidence-count gap
(Finding 2) is not exactly an "inconsistency" (both numbers are real,
correct measurements of *different points in time*) but is undocumented
drift that a reviewer could reasonably mistake for an error if they ever
gained repo access and queried the DB themselves.

## J. Experimental design weaknesses

Finding 1 (top of list). Claim-decomposition experiment better described
as counterfactual reanalysis (C). No dev/test split for any deterministic
validator check. $n=9$ throughout limits everything downstream. Baseline
4 (TruthLens minus validation) has never been run as its own timed pass
(already disclosed).

## K. Statistical weaknesses

Wilson CIs and McNemar used appropriately for the sample sizes involved;
no p-values from underpowered tests presented as significance claims
(already correct practice in the current paper). No power analysis
existed before Day 10's self-audit added one sentence; still no formal
pre-registered minimum-detectable-effect calculation.

## L. Terminology problems

Full audit deferred to a dedicated pass (Phase 19) since it requires
re-reading the whole paper against a checklist — flagged as the next
concrete task. Spot-checked this pass: "guarantee" (3 uses) — legitimate,
refers to a deterministic code invariant, not an empirical claim, no
change needed. "Trustworthiness" is used as the paper's central construct
without a single formal operational definition anywhere — confirmed
absent on re-read of Sections IV, IX, and the Conclusion. This is real
and matches Phase 3's concern exactly.

## M. Reproducibility problems

Finding 2 (new). Previously-disclosed gaps (unseeded LLM calls, no
unified docker-compose) remain accurate and unchanged.

## N. Reviewer attack points (ranked)

1. "Your baselines were given a cleaner claim than TruthLens ever
   produces for itself — your headline comparison doesn't isolate
   architecture the way your methodology section claims." (Finding 1 —
   the single most damaging attack available against this paper as it
   currently stands.)
2. "$n=9$, $n=6$ paired, is far too small to support any of your
   comparative claims, regardless of how honestly you caveat them."
3. "Your 'ablation' in Section VIII is a reanalysis of existing data, not
   an independently-run experiment — the label oversells it."
4. "'Trustworthiness' is never formally defined — what exactly did you
   measure?"
5. "Your validator's best-performing new check was calibrated on the
   exact data used to report its recall."
6. "No inter-annotator agreement anywhere in the paper."

## O. Recommended experiments (priority order)

1. **Re-run Baselines 1–3 against TruthLens's actual extracted claim
   text** (pull `claim_ids_extracted`/real `Claim.text` per item from the
   validator-audit run or a fresh extraction pass) instead of
   `items.jsonl`'s hand-written summary. This is the single highest
   -priority fix — it directly determines whether the headline finding's
   interpretation is defensible at all.
2. Build the validator dev/test split (Phase 4) with synthetic adversarial
   cases, frozen before evaluating Check 4/5.
3. Entity-consistency validator (Phase 5), evaluated independently, not
   assumed beneficial.
4. Error budget / earliest-causal-failure analysis (Phase 11) — high
   value, fully achievable from data already collected plus the raw DB
   now confirmed live.
5. A committed, reusable query/script scoping the live DB to exactly the
   9 benchmark items' correct `reels.id` values, to close Finding 2 and
   make the evidence-quality numbers genuinely re-derivable going forward.

## P. Recommended paper changes

Do not touch the paper until (O.1) is resolved or explicitly deferred
with disclosure — presenting the current headline number without at
least flagging Finding 1 would be a real, avoidable honesty gap. Beyond
that: formally define the central construct (Phase 3); relabel Section
VIII's experiment; add Finding 1/2 to Threats to Validity immediately
regardless of whether O.1 is completed, since the paper is inaccurate
about baseline design *right now* independent of any new experiment.

---

## What this audit did not yet cover

Full terminology sweep (Phase 19), related-work comparison table
(Phase 20), figure redesign (Phase 22), page-count trim (Phase 23), and
the three-reviewer/area-chair simulation (Phase 26) are all still
pending and depend on the above being resolved first — running them now
would mean reviewing a paper that Finding 1 already shows needs to change.
