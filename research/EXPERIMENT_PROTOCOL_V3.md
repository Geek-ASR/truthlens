# EXPERIMENT PROTOCOL V3 — one more experimental iteration of TruthLens

**Status: pre-registration. Frozen before any V3 run produces output.**
Git-tag this commit `experiment-protocol-v3-frozen`; every result row records the config git SHA.

This protocol was designed by a multi-agent design pass (5 design agents) and
reconciled by the author against two adversarial roles (rigor, feasibility) after
the workflow's own verifier agents hit a session limit. It supersedes nothing in
`METRICS.md`; it adds `METRICS_ADDENDUM_V3.md` (12 new/clarified metric
definitions) and pre-declares the analysis.

---

## 0. Honest framing — this is post-registered, not blind

The claim-extraction v2 design is **informed by aggregate error categories from
the already-published 3B local-only run** (`local_eval_v2.jsonl`, the paper's
current floor): the six failure *types* below, the 11 affirmative-verdict-on-false
items, and the two verdict-stage cases (item-0116, item-0111) were all read off
that run. Therefore:

- We do **not** claim "developed blind to the validation set." We claim: the v2
  prompt and filters are motivated by (a) those aggregate categories and (b) the
  claim-detection / check-worthiness NLP literature; they are tuned **only** on
  the 9-item `dev` split plus a hand-authored synthetic diagnostic set; and the
  193-item run is **one held-out confirmation shot**, not a blind first look.
- The v2 prompt string, `CLAIM_EXTRACTION_PROMPT_VERSION`, and the deterministic
  post-filter module are frozen in **one commit**, SHA cited in the paper,
  before any 193 output is read.
- Expected effect **direction** per failure type is pre-declared in §3.3.
- Dev-set and diagnostic-set numbers are the development evidence; the 193 number
  is the single confirmation.

The frozen n=6 comparison in the paper stays on prompt **v4 forever**. v5 is
never run on the 6/9 dev items for an "updated comparison" — that would
contaminate the frozen result. (`STATUS.md` already commits to this.)

---

## 1. Scope of this iteration

Ordered deliverables:

1. **Metrics addendum** (`METRICS_ADDENDUM_V3.md`) committed & dated — done in this commit.
2. **Claim-extraction v2**: 8B model for the extraction stage only + rewritten
   prompt (v5) + deterministic post-filter. Frozen after passing §3.4 gates.
3. **Full-system runs on all 193 validation items** (local-only, $0):
   - **C0** = 3B + v4 — the existing frozen `local_eval_v2.jsonl`. Not re-run;
     derived metrics recomputed under the addendum.
   - **C1** = 3B + v5 + filter — NEW, full 193. Isolates the *method* effect at
     fixed model size (~5–6 h).
   - **C3** = 8B-extraction + v5 + filter — NEW, full 193. The improved
     configuration (~10–14 h; 8B only at the claim-extraction stage, downstream
     stays 3B).
   - **C2** = 8B-extraction + v4 — dev + a frozen stratified 40-item validation
     subsample only. Gives the model×method interaction without a second
     multi-night 8B run.
   - **Post-filter on/off** is a free ablation on every config (re-run the
     deterministic filter over frozen extractions + re-score; zero new LLM calls).
4. **Baselines on all 193** — B1 (LLM-only), B2 (Search+LLM), B3 (Search+RAG+LLM),
   each in two claim conditions (§5). Verdict call on **3B** (matches C3's
   downstream). Shared on-disk search cache.
5. **Report**: coverage / balanced accuracy / macro-F1 / per-class F1 / support
   validity / evidence quality, per the addendum, in one primary comparison table.
6. **Second-pass annotation** (§6): deterministic n=56 subsample, intra-project
   LLM-assisted, disclosed as *not* an independent-human IAA study.
7. **Provenance no-claim adjudication** (§7): the 126 (→ new count) no-claim items
   binned (i)/(ii)/(iii) against the actual ingested text channels.
8. Rewrite the affected paper sections to the branch selected by §8, recompile,
   commit.

Out of scope this iteration (named as open work): vision-first extraction path;
paid cloud-escalation tier; a genuine independent-human annotator corps.

---

## 2. Retrieval held constant — shared evidence cache

`run_local_eval.py` and the baseline scripts re-execute live DuckDuckGo search
every run. That confounds the 3B↔8B and system↔baseline contrasts with web
variance, and ~1,000–2,500 added baseline searches from one residential IP invite
non-reproducible rate-limiting.

**Mitigation (must land before any V3 run):**

- A shared on-disk cache: `research/results/v3_search_cache/{sha1(query)}.json`
  (query → ranked `SearchResult` list, each with `title`, `url`, `snippet`,
  `full_content`, `fetched_ok`) and `.../v3_page_cache/{sha1(url)}.txt`
  (URL → extracted page text, capped at the pipeline's own `_MAX_PASSAGE_CHARS`).
- Every V3 config — C1, C3, C2, the three baselines × two conditions — reads
  through this cache. A cache **miss** does one real fetch with a fixed polite
  delay (≥ 2 s) and writes back. Runs are checkpointed and resumable.
- The cache is populated in **one contiguous run window** so DuckDuckGo drift
  cannot separate configs. B2 (`.snippet`) and B3 (`.full_content`) share the
  same cached results, so B2 vs B3 differ **only** in snippet-vs-fulltext.
- `research_planning` is model-dependent, so C1 (3B) and C3 (8B-extraction) can
  emit different query sets. Disclosed: the C3 number folds in whatever residual
  retrieval variance the differing query sets cause; the shared cache removes it
  for every *repeated* query, which is the large majority.
- LLM sampling: temperature 0 (greedy) for every stage in every config if the
  Ollama provider surfaces it without out-of-scope changes; otherwise one run per
  config, identical across configs, single-run local-model variance disclosed as
  a limitation the reference numbers share. **No config is ever re-run to keep a
  better result.**

---

## 3. Claim-extraction v2 spec

### 3.1 Model

`LLM_MODEL_CLAIM_EXTRACTION = "llama3"` (Llama-3 8B, `llama3:latest`, already
pulled) **for the claim-extraction stage only**. `LLM_MODEL_RESEARCH_PLANNING`,
`LLM_MODEL_EVIDENCE_ANALYSIS`, `LLM_MODEL_VERDICT` stay on `llama3.2` (3B).

Rationale: the paper's floor localised the binding constraint to claim extraction
(0% research-failure; ~2/11 affirmative errors were verdict-stage). Spending the
larger model only there keeps the measured delta attributable to that stage and
keeps compute feasible on 8 GB RAM (a smoke test measured ~90 s cold / >40 s warm
per 8B structured call; all-stages-8B on 193 is 14–33 h and OOM-risky).

Dev-time fallback order if the §3.4 conformance gate fails: `llama3` → `mistral`
(7B) → `llama3.2` (3B, keep v5 prompt + filter). Chosen on the 9 dev items only.

### 3.2 Prompt changes (v4 → v5), each tied to one failure type

| ID | Failure type | Change (summary) |
|----|--------------|------------------|
| P1 | (a) fragments with no assertion structure | Mandatory predicate/falsifiability test before `verifiable=true`: a verifiable claim is a complete declarative proposition (subject + asserting predicate) for which the model can state what evidence would confirm/refute it. Fragments, questions, greetings, bare noun phrases/slogans, commands, garbled text are **never** verifiable; if that is all there is, return an empty `claims` list. |
| P2 | (b) verbatim recitations | Do not extract a claim from a recitation of a well-known fixed text (anthem, pledge, oath, prayer, scripture, song). At most one `verifiable=false` claim that the recitation occurred. |
| P3 | (c) latching onto a true side-fact | Primary-claim step: first identify the single assertion the post exists to make (`importance ≥ 0.8`); incidental/background facts only as separate claims at `importance ≤ 0.4`, never in place of the primary claim. |
| P4 | (d) extracting the debunk framing | Extract the claim the post **asserts/amplifies**, phrased as the assertion — not any debunk/correction/"this is false" framing present in the content or as an on-screen stamp. If content is only a correction and the underlying claim can't be recovered, extract nothing. |
| P5 | (e) provenance claims dropped as "can't see the video" | PROVENANCE CLAIMS section: when the caption/OCR/narration tells the viewer what a video/image shows, extract a claim of the fixed form *"The [video/image] shared in this post is presented as showing [subject/action] [at LOCATION] [on/around DATE], as the post states."* — `verifiable=true`, `claim_type=factual`, `importance ≥ 0.8`, populate `location`/`time_reference`, `source_quote` = the exact caption/OCR line. Inability to view the media is **not** evidence about the claim and must not lower verifiability. A thin/absent transcript does not mean there is no claim — the caption/OCR carry it. |
| P6 | (f) non-English fragment | Extract every claim as a fluent English proposition; do not copy an untranslated fragment as the claim text. Do not extract fewer claims because a language is harder to parse. Distinguish "not English" from "not intelligible" — skip a genuinely garbled passage, but still extract from any intelligible caption/OCR. |
| P7 | (a)/(b)/(d) output-contract | An empty `claims` list is a valid, correct outcome. Do not manufacture a claim to avoid returning nothing. |

**Why these are mechanism-level, not item-fit:** each rule encodes a general
property of what is check-worthy (subject+predicate+falsifiability; the
performative/assertive distinction; salience ranking; the metalinguistic/asserted
distinction; "verifiable = evidence *could* be gathered", not "the model can
confirm it now"; multilingual normalization). Illustrative examples in the prompt
are invented generic grammatical classes, **never** literal transcript strings
from any 193-item row. Concrete token/text lists live in the deterministic
filters, authored from general knowledge (see §3.3).

### 3.3 Deterministic post-filter (`claim_extraction_postfilter.py`, frozen)

Runs inside `extract_claims` after dedup, before persistence. Every firing is
written to `record_audit(action="claim_extraction_postfilter", …)`. A demoted
claim row is **still persisted** with `verifiable=false` — never silently
dropped.

| Rule | Effect | Deterministic | Compares against |
|------|--------|---------------|-----------------|
| **F1** triviality / no-predicate | demote `verifiable→false` if word-count < 6 OR no predicate signal (verb-lexicon / `-ed`/`-ing` heuristic), AND no proper-noun subject and `entities` empty, AND model's own `extraction_confidence < 0.5` or `importance < 0.5`; unconditional if ends with `?` or is fully quoted and < 8 words | yes | the claim text only |
| **F2** fixed-text recitation | demote if token-Jaccard of `text` or `source_quote` vs any entry in a small static corpus (US Pledge; opening lines of common anthems incl. Jana Gana Mana; Preamble to the Indian Constitution; Gayatri Mantra; Lord's Prayer; common oaths) ≥ 0.6 | yes | a frozen in-repo corpus authored from general knowledge |
| **F3a** debunk-framing | demote if normalized `text` contains a phrase from a frozen metalinguistic marker list ("actually", "in reality", "no evidence that", "did not actually", "was falsely", "is misleading", "old video", "was debunked", "the video does not show", …) | yes | the claim text only |
| **F4** `source_quote` sanitation | if `source_quote` is non-empty and is not a verbatim normalized substring of transcript/OCR/caption/`visible_text_or_graphics`, set it to `None` (do **not** demote — P5 provenance claims are summaries and may legitimately lack an exact quote) | yes | the reel's own channels only |
| **F5** incidental demotion | over one reel's verifiable+factual claims, demote a claim only if another verifiable claim exceeds its `importance` by ≥ 0.3 **and** this claim's `importance` ≤ 0.3. Never removes the highest-importance verifiable claim; never empties the set. | yes | within-reel importances only |

**F3b (article-echo leak guard) is CUT.** The design proposed comparing extracted
claims against `review_batch.jsonl` / fact-check article text. That makes the
system consult the answer key at inference time on output that is then scored —
**fatal contamination**. Failure type (d) is handled by P4 + F3a (markers in the
claim's own text), not by any comparison to fact-check-derived text. A unit test
asserts the post-filter module opens **no** dataset/ground-truth/fact-check file.

Effect on `outcome_type`: F1–F3a can push an item to `no_verifiable_claims` only
when the demoted claim was its *sole* verifiable claim — which is the honest
bucket under METRICS.md (excluded from the accuracy denominator, reported as its
own rate). F4/F5 never change `outcome_type`. The harness logs
`n_verifiable_pre_filter`, `n_verifiable_post_filter`, and which rule fired, per
item, so the report gives the outcome distribution both with and without the
filter from the one run.

### 3.4 Freeze gates (all six pass, using zero validation-set output)

1. **Schema-conformance** — 27 dev calls (9 items × 3, chosen model + v5 prompt,
   real `OllamaProvider.structured_call`): 27/27 parse to
   `ClaimExtractionResult`, no retry-exhausted `ProviderError`, 0 invented
   `claim_type` values, ≤ 1 boundary-clamp, 0 truncations (`done_reason=="stop"`
   every time, `num_predict=8192` never hit). Record median + p90 latency.
   Fall back `llama3 → mistral → llama3.2` on failure.
2. **Dev-behavior** — on the 9 dev items, v5+filter shows no regression vs v4:
   ≥ 4/5 dev provenance items now yield a verifiable provenance claim; clean/quote
   controls still extract; the v4 prompt-injection defence still holds.
3. **Diagnostic** — ≥ 17/20 hand-authored fixtures in
   `backend/research/claim_extraction_v2/diagnostic_set.jsonl` match expected
   behavior; every miss documented in `FREEZE.md`. Fixtures are invented or drawn
   from pre-2023 globally-famous non-Indian-political miscontextualized-media
   cases (e.g. the 2017 "shark on the flooded highway" hoax) — zero benchmark
   items. Coverage: 4× type (a), 3× (b), 3× (c), 3× (d), 4× (e), 3× (f), + 1 clean
   control + 1 injection control.
4. **Filter-determinism** — pytest for F1–F5 (≥ 2 positive + 2 negative each) all
   green; running the filter twice on one input is byte-identical.
5. **Artifacts committed** — `prompts.py` v5 string with
   `CLAIM_EXTRACTION_PROMPT_VERSION="claim_extraction.v5"`; the post-filter module
   + frozen corpora/lexicons; `config.py` model set; `diagnostic_set.jsonl`;
   `FREEZE.md` recording model, the 27-call numbers, the diagnostic score, every
   threshold, and the git SHA.
6. **Tag + single run** — `git tag claim-extraction-v2-frozen`, then run each
   config exactly once (§4). No prompt/filter/model change after the tag; any
   defect found mid-run is logged and, if fixed, requires a `v2.1` re-freeze and a
   **new** run — the v2 numbers stand as reported.

### 3.5 Harness recording change (land before freeze)

`run_local_eval.py` currently records only `validation_status` and `verdict`. Add
persistence of the **raw pre-validation `VerdictProposal`** (label, confidence,
`reasoning_summary`, `cited_evidence_ids`) alongside the validated outcome — the
same `SKIP_VALIDATION=True` + still-compute-`validate_verdict()` pattern the
validator audit used. Needed for the *without-validation* unsupported-output rate
(METRICS.md §3). Generic recording change, committed and dated before the freeze.

---

## 4. The full-system runs

| Config | Model (extraction / downstream) | Prompt | Filter | Set | Output file | Est. |
|--------|-------------------------------|--------|--------|-----|-------------|------|
| C0 | 3B / 3B | v4 | none | 193 (frozen) | `local_eval_v2.jsonl` (exists) | — |
| C1 | 3B / 3B | v5 | on | 193 | `local_eval_v3_c1_3b_v5.jsonl` | ~5–6 h |
| C3 | 8B / 3B | v5 | on | 193 | `local_eval_v3_c3_8bx_v5.jsonl` | ~10–14 h |
| C2 | 8B / 3B | v4 | none | 9 dev + 40-item frozen subsample | `local_eval_v3_c2_8bx_v4.jsonl` | ~3–4 h |
| — filter-off | recompute from C1/C3 frozen extractions | — | off | 193 | `*_filteroff_scores.json` | free |

**C2 subsample** = a stratified 40 of 193, selected deterministically **before**
C2 runs (stride over sorted `item_id` within `ground_truth_label` × `platform`
strata; exact list committed to `research/dataset/c2_subsample.txt`). C2 exists
only to separate model effect (C0→C2) from method effect (C0→C1) from combined
(C0→C3) on a common set; it is never a headline number.

**Run-once discipline:** first terminal outcome per `item_id` wins; a resume only
backfills missing `item_id`s; **no item is re-run after its output has been
inspected.** After each run, assert every `item_id` has exactly one terminal row.
Config git SHA in every row.

If the §3.4 gate forces `mistral` (7B) instead of `llama3` (8B), C3's label
becomes "7B-extraction" throughout and the paper says so.

---

## 5. Baselines on all 193

B1 `baseline_llm_only`, B2 `baseline_search_llm`, B3 `baseline_search_rag_llm` —
each run **once per verifiable claim**, then per-claim labels collapsed to one
reel-level label by the **real** `app.pipeline.overall_verdict.derive_overall_verdict`
(never a re-implementation), exactly as `RECONSTRUCTED_RESULTS.md` fixed the n=6
comparison. Verdict LLM call on **3B** (matches C3 downstream). Search via
`DuckDuckGoSearchProvider` through the §2 shared cache.

### Two claim conditions

- **SHARED** *(headline)* — every config (C3 full system, B1, B2, B3) receives
  the **identical frozen v5 8B-extraction verifiable claims** for that item, from
  `local_eval_v3_c3_8bx_v5.jsonl`. On an item where v5 extraction yielded **no**
  verifiable claim, the baseline model is **not called**; the row is
  `outcome_type="no_verifiable_claims"`, `predicted_label="UNVERIFIED"`, and lands
  in the **same denominator** as the full system. A baseline never receives a
  claim the system did not have. This is the RQ2 comparison in the form the
  claim-input correction requires — claim extraction identical across every
  configuration, so a reel-level difference is attributable to downstream
  architecture.
- **ORACLE** *(labeled upper bound, never the headline)* — every config, including
  the full system with stage-2 extraction **bypassed**, receives the reviewer's
  `ground_truth_claim` as the sole claim (`importance=1.0`). Isolates
  verdict+retrieval quality given a perfect claim. A mandatory **pre-run
  neutrality audit** of all 193 `ground_truth_claim` strings (applied blind to any
  config output, logged) strips wording that reveals the fact-checker's
  conclusion while keeping the claim's own assertion (≈ 5 currently carry
  "is an old video" / "the clip is not edited" / "while X is permitted" framing).

### Fairness (confounds addressed)

C1 claim-input asymmetry (removed — both conditions feed every config the same
claim); C2 Gemini-rescue (removed — `GEMINI_API_KEY` unset; baselines construct
`OllamaProvider()` directly, never the factory); C3 search-infra asymmetry
(removed — one shared cache, same fetch/extract path, same char cap); C4
retrieval-**budget** asymmetry (**deliberately kept and labeled** — B2/B3 issue 1
verbatim query/claim, the full system issues 5 planned queries/claim;
`research_planning` is a stage under test, so the 1-vs-5 count is the independent
variable; `n_search_queries` recorded per row); C5 prompt asymmetry (removed —
baseline prompts frozen at their committed `.v1` text, never tuned on v2 items);
C6 aggregation asymmetry (removed — identical `derive_overall_verdict`); C7
scoring asymmetry (removed — one scorer, formulas untouched); C8 item-set/order
(removed — same 193, same `_norm_url` match, fixed order, resumable);
C9 non-determinism (temperature 0 or single-run-symmetric, never best-of);
C10 oracle leakage (the neutrality audit + ORACLE labeled non-comparable);
C11 search-failure accounting (baseline harness applies `run_local_eval.py`'s
exact reel rule — `research_failed` only if *every* verifiable claim's search
infra-failed).

### Harness changes (must land before running)

- `common.py`: `load_dataset_v2()` reading `items_v2.jsonl` with
  `id←item_id`, carry `ground_truth_label`/`ground_truth_tier`(=1)/`platform`/
  `language`; drop `claim_text` references. `load_frozen_extraction(path)` →
  `{item_id: [(claim_text, importance), …]}` keeping `per_claim` with
  `verifiable is True`. `resolve_claims(item, condition, index)`.
  `aggregate_reel(per_claim_results)` importing the real `derive_overall_verdict`
  with local `_FakeClaim(importance, status=extracted)` / `_FakeVerdict(label)`
  dataclasses; reel rule mirrors `run_local_eval.py._eval_one` exactly.
  `enforce_local_only()` — `sys.exit` unless `GEMINI_API_KEY==""` and
  `SEARCH_API_KEY==""` and `LLM_PROVIDER=="ollama"` and
  `SEARCH_PROVIDER=="duckduckgo"`; assert constructed providers are
  `OllamaProvider` / `DuckDuckGoSearchProvider`.
- Each baseline script: `load_dataset()` → `load_dataset_v2()`; argparse
  `--condition {SHARED,ORACLE}`, `--extraction-file`, `--limit`, `--only`,
  `--resume`; call `enforce_local_only()`; the SHARED no-claim branch writes the
  row without calling the model.
- `run_local_eval.py`: `--oracle-claims-from items_v2.jsonl` (bypass
  `extract_claims`, insert one `Claim(text=ground_truth_claim, verifiable=True,
  importance=1.0, …)`); surface `importance` in each `per_claim` dict;
  `--out`, `--config-label`; echo resolved `LLM_MODEL_*` set to stderr and the
  output file's first line.
- `score_local_eval.py`: `--results/--report/--scores/--items` (defaults = current
  v2 paths, so frozen scoring is unchanged); `--paired-against OTHER.jsonl` →
  McNemar exact 2×2 + p over the shared resolved set.
- New `run_all_baselines_v2.py` driver + `compare_configs.py` → one
  `BASELINE_V3_COMPARISON.md` table.
- Unit-test the v2 adapter on 3 rows before any batch.

---

## 6. Second-pass annotation

### 6.1 Deterministic subsample (n = 56)

Sort all 193 `item_id`s ascending (lexical == numeric). **Core (n = 38):** every
item at 1-indexed position `p` with `p mod 5 == 0` (checked: no period-5 aliasing
against factchecker/claim_type/language/annotation_status/label). **Census
add-ins (unioned):** (a) all 11 affirmative-verdict-on-FALSE/MISLEADING items;
(b) all 4 ground-truth-TRUE items; (c) all 7 resolved MISLEADING items. Dedupe →
56. A ~15-line `make_second_annotator_subsample.py` re-derives (a)/(b)/(c) from
`local_eval_v2.jsonl` + `items_v2.jsonl`, writes
`research/dataset/second_annotator_subsample.txt`, asserts `len == 56`.

**Report split:** compute agreement on the **full 56** *and* on the **unbiased
n=38 core** separately; the core statistic is the one that generalizes to the
193-corpus, the enriched 56 is a lower bound on the rare boundaries.

### 6.2 Protocol

A second, **blind** derivation of each subsample item's one-sentence claim,
anchoring verbatim quote, and label, from the professional fact-check
(freshly re-fetched). Must differ from pass 1 on: operator (a different project
member, or the same person after a ≥ 4-week washout — stated in the paper), model
(a different family from pass 1's `llama3.2` and from the evaluee's model, used to
**draft** only), prompt (from scratch, article-first). Blind to: pass-1's claim /
quote / label / claim_type / decision log, **and** the pipeline's own
`claim_texts_extracted` / `predicted_label` / `overall_reasoning`. May see: the
re-fetched article; the frozen retrieved post text; the `VerdictLabel` taxonomy;
the `claim_type` vocabulary. Both the A2 model proposal and the final A2 value are
stored (within-A2 override rate = "how much is the assist doing").

Reconciliation: a script diffs pass-1 vs A2; every mismatch is adjudicated by the
lead author against the re-fetched article with a reason code {pass-1 error / A2
error / genuinely ambiguous / both acceptable paraphrases}. **If pass-1 errors are
found, `items_v2.jsonl` is corrected, `score_local_eval.py` re-run, and the delta
logged loudly in `STATUS.md` + Threats to Validity — fix + re-run + disclose, not
foot-note.**

### 6.3 Metrics

- **Headline:** label agreement on the 3-way bucket — report **PABAK / Gwet's
  AC1** (headline; Cohen's κ is suppressed by the 83% FALSE base rate — the kappa
  paradox), plus Cohen's κ, raw % agreement, and the full A1×A2 confusion matrix
  with off-diagonal cells listed by `item_id`. CI by deterministic item-level
  bootstrap (fixed index schedule) or analytic SE. On both n=56 and n=38.
- Fine-label κ over the 8-value taxonomy; FALSE-vs-not-FALSE κ + raw agreement
  (the boundary every balanced-accuracy denominator hinges on).
- **Claim-adequacy rate:** fraction of the 56 where A1's `ground_truth_claim`
  captures the same specific check-worthy assertion (blind judge, yes/partial/no,
  reason codes {too broad, too narrow, wrong subject, states the fact-check's
  framing, paraphrase drift}); same rate for A2's own sentence as a
  task-difficulty control.
- **Headline-metric sensitivity:** recompute bucketed accuracy / balanced
  accuracy / macro-F1 / MISLEADING recall on the subsample under A1 vs
  A2-adjudicated labels; report the deltas as the practical bound on how much
  label-mapping choices move the §VII-D numbers.
- Anchor-quote validity rate (A1 quote found verbatim in the re-fetched article
  **and** actually states the mapped verdict); claim-type κ (diagnostic).

### 6.4 Disclosure language (verbatim into the paper)

> The claim phrasings and labels for the TruthLens-202 validation split were
> produced by a single project reviewer with local-LLM assistance. To bound that
> step we ran a second, blind re-annotation over a deterministic 56-item
> subsample (every fifth item by sorted id, unioned with a census of the 11
> affirmative-verdict-on-false items, the 4 ground-truth-TRUE items, and the 7
> resolved MISLEADING items), with a different operator, a different model, and a
> from-scratch article-first prompt, blind to the first pass and to the
> pipeline's output. **This is intra-project, LLM-assisted re-annotation, not an
> independent-human inter-annotator study**, and we do not report the statistic
> as a conventional IAA κ. It bounds the reproducibility of the
> article→taxonomy mapping (AC1 = …), the adequacy of the first pass's claim
> sentences (… [CI]), whether the coverage-vs-verdict reading of the 11 items
> survives blind re-rating (…/11), and an upper bound on how far the §VII-D
> metrics move under the second pass's labels (≤ … pts). It does **not** bound
> error shared by both passes, the correctness of the professional fact-checks,
> or inflation from correlated model priors. A genuine independent-human
> annotator corps remains the top open item.

Everywhere the number appears it is labelled "intra-project LLM-assisted
re-annotation agreement", never "inter-annotator agreement".

### 6.5 Blind re-rating of the affirmative-on-false items

Script-generated packets from allow-listed fields only: the post's retrieved text;
the **adjudicated** one-sentence claim + verdict (not pass-1's phrasing — it is
under test); the pipeline's actual `claim_texts_extracted` (each with `verifiable`
+ per-claim verdict) and `overall_reasoning`. **Not** shown: the prior
coverage-vs-verdict rating, the "~9/2" framing, any count. Two raters, no LLM (or
a from-scratch LLM prompt not told the expected distribution). Rubric: Q1 "is the
verdicted claim a faithful restatement of the post's central checkable
assertion?" (yes/partly/no) → Q2 (only if Q1=yes) "did the verdict stage affirm
it?" → **CC** (coverage failure) / **VS** (verdict-stage failure) / **MIX** /
**IND**. Lead author adjudicates. If the adjudicated split differs materially
from the paper's informal ~9 CC / ~2 VS (e.g. 6/5), §VII-D and the abstract are
corrected to the adjudicated numbers and the change logged in `STATUS.md` +
Threats.

---

## 7. Provenance no-claim adjudication

The (post-v5) `no_verifiable_claims` items **cannot** be reported as a monolithic
"extraction failure" rate: ~80% of the corpus is provenance-type, and for a
text-only pipeline "no text-checkable claim" is sometimes the *correct* output.

**Pre-registered rubric** (frozen here, before any v5 output). The second
annotator adjudicates every post-v5 `no_verifiable_claims` item (all, or a
stratified ≥ 60 by `claim_type` × `language`), judging **against the actual
ingested transcript/OCR/caption strings** (not the `claim_type` label, which is
itself single-annotator):

- **(i) correct scope-limited abstention** — the checkable assertion is genuinely
  absent from all three text channels; the falsehood is purely visual. Reported as
  an *architectural scope limit* (no provenance/vision module), **not** an
  extraction bug. Requires a *positive* finding of absence in all three channels,
  verified against the strings — never inferred from `claim_type=provenance`.
- **(ii) genuine text-coverage failure** — the assertion **is** in the post's own
  text and the extractor missed it or wrongly dropped it. A real system failure.
- **(iii) degraded input / other** — non-English fragment, OCR garble, verbatim
  recitation.

**Report two numbers, not one:** the raw non-response rate ("in deployment the
system says nothing on N% of posts, whatever the cause") **and** an adjusted
text-coverage-failure rate = `(ii) / (items with a text-checkable claim
present)`. **Lead with the adjusted number**; present the raw rate as deployment
reality. State that (i) is "correct given the text-only input contract" — a fuller
system with reverse-image search would find those claims checkable — so it is not
correctness in general. Put PABAK/AC1 on the (i)/(ii)/(iii) assignment; flag it
single-annotator-plus-one-check, not settled.

P5's whole purpose is to move items out of (i) into "resolved"; the pre/post-v5
shift on provenance items is the mechanism test.

---

## 8. Pre-declared analysis — falsification criteria

**Headline under test:** *"With a local-only TruthLens, claim extraction — not
evidence retrieval and not verdict reasoning — is the binding constraint on
whether short-form political misinformation gets checked at all."*

**"Material change" rule:** a C0→C3 (or C0→C1) move on a proportion counts as
material only if the Wilson 95% CI of the new estimate **excludes** the C0 point
estimate; for balanced-accuracy figures the bootstrap 95% CI (B = 10,000) must
exclude the C0 point. Otherwise "no change".

**Adjudicator metrics:** "did it get better end-to-end" is judged on **corpus
bucketed accuracy** (/193; C0 = 10.4%) and **corpus balanced accuracy** (/193;
C0 = 12.3%) — denominator-stable across configs. Resolved-only accuracy is
secondary and always read with its shifting denominator noted. "Is extraction the
gate" is judged on **verdict resolution rate** (C0 = 34.7%) cross-checked against
human **Claim Recall** — both must move together.

**CONFIRMS** the headline (extraction was the gate and is at least partly
relievable within local-only means) if **all**: resolution rate C3 ≥ 55% with
Wilson lower bound > 34.7%; Claim Recall rises ≥ 15 pts with non-overlapping CIs
and Claim Precision stays ≥ ~0.5 and empty-claim-text rate < ~5%; resolved
bucketed accuracy C3 ≥ 29.9% (CI not below C0) and corpus bucketed accuracy Wilson
lower bound > 10.4% and corpus balanced accuracy > 12.3% moving toward 33.3%;
`research_failed` ≤ ~3% and usable-evidence rate within noise of the C0 sample.

**CONFIRMS the STRONGER form** (text-only local extraction is a model-capability
wall; vision-first is the necessary next lever) if: resolution rate C3 < 45% (CI
overlaps 34.7%) **despite** 8B + v5 + filter; Claim Recall stays < ~40%,
Provenance Claim Recall near the floor; and residual `no_verifiable_claims` items
still fall in the pre-listed failure types.

**FALSIFIES** the headline if **any**:

- **(a) coverage opens but correctness doesn't** — resolution rate C3 ≥ 55% BUT
  resolved bucketed accuracy ≤ 25% and resolved balanced accuracy ≤ 33.3% and
  corpus balanced accuracy not materially above 12.3%. → the extraction gate was
  masking a downstream constraint; rewrite to "claim extraction gates *coverage*;
  verdict reasoning gates *correctness*."
- **(b) filter, not model** — resolution rate C3 stays < 45% BUT human Claim
  Recall on the same items ≥ 60% (the model names the right proposition; the
  verifiability/grounding/post-filter discards it). → constraint is the
  verifiability gate, movable without a bigger model.
- **(c) retrieval becomes co-binding** — C3 `research_failed` > 10% OR usable-
  evidence rate drops materially below the C0 sample. → the "not retrieval" clause
  is falsified.
- **(d) architecture adds nothing once extraction is held constant** — baselines
  fed the SHARED v5 claims reach corpus bucketed accuracy within 3 pts of (or
  above) C3 at a similar resolution rate, overlapping CIs, zero McNemar discordant
  pairs favoring the full system. → does not falsify "extraction is the
  constraint" but falsifies any implicit "the architecture is what pays off once
  extraction is fixed"; **reported with equal prominence.**
- **(e) the gain is a mirage** — corpus bucketed accuracy C3 rises but Claim
  Precision collapses (< ~0.35) OR the "trivially-true fragment extracted then
  verified" pattern recurs on C3 at a similar-or-higher rate (manual read of every
  FALSE/MISLEADING → affirmative resolved case).

**INCONCLUSIVE band** (report as directional, underpowered, NOT a confirmation):
resolution rate C3 in 45–55% with CI overlapping 34.7%; OR any adjudicator-metric
CI overlapping the C0 point; OR resolved accuracy 25–30% with balanced accuracy
straddling 33.3%.

The rewrite of the abstract contribution sentence and the §VII-D "what this is,
and is not" paragraph for **each** branch is drafted **before** the C3 numbers are
looked at; only the branch the frozen run selects is kept.

---

## 9. Metric compliance

See `METRICS_ADDENDUM_V3.md` (this commit) for the 12 definitions pre-registered
before the freeze: balanced accuracy (both denominators, bootstrap CI);
corpus-level bucketed accuracy; the false-abstention relabel + the new
declined-to-answer / non-response rate; macro-F1 scope ("classes with non-zero GT
support OR non-zero predictions", plus the full-8-class value for transparency);
verdict resolution rate & no-checkable-claim rate formulas; the baseline
extraction-source condition (one call per verifiable claim, aggregated by
`derive_overall_verdict`, extraction source ∈ {C1-3B-v5, C3-8B-v5, oracle-GT});
the ORACLE reference row as labeled non-comparable; claim-extraction stage
instrumentation; `is_visual_claim` handling (add the tag in the annotation pass,
else Provenance Claim Recall stands as the proxy); support-validity stratified
sampling; constant-predictor references on both denominators;
`ground_truth_tier=1` backfill rule (done this commit).

---

## 10. Feasibility (author estimate, informed by a smoke test)

3B smoke anchor: the C0 run summed to 5.48 h latency (mean 102 s/item, median
11.7 s, max 907 s; ~1.5–2.5 h of that is network I/O). 8B smoke: ~90 s cold /
> 40 s warm per structured call on this 8 GB M1.

| Work | Estimate |
|------|----------|
| Engineering: shared search cache + v2 baseline adapter + recording change + filter module + diagnostic set | ~1–1.5 days |
| Freeze gates (27 dev calls + diagnostics + pytest) | ~2–4 h |
| C1 (3B + v5) × 193 | ~5–6 h |
| C3 (8B-extraction + v5) × 193 | ~10–14 h |
| C2 (8B-extraction + v4) × 49 | ~3–4 h |
| Baselines B1/B2/B3 × {SHARED, ORACLE} × 193, verdict on 3B, cached search | ~15–30 h |
| Scoring + figures + comparison table | ~3–4 h |
| Second-pass annotation + provenance adjudication + re-rating (LLM-assisted) | ~1–2 days |
| Paper rewrite to the selected branch + recompile + verify | ~0.5–1 day |

**Honest total: ~5–7 days**, mostly unattended compute plus the annotation
passes, on the constraint that everything after the freeze runs on one frozen
code state.

**Biggest residual risk:** the improved configuration is still deliberately weak
(local, 3B downstream, cloud escalation off, keyless search); "an 8B model fails
to extract a checkable claim from a large fraction of provenance posts" is close
to expected, and a reviewer can fairly say the bottleneck may be an artifact of
the chosen configuration until the vision-first and cloud tiers exist — which this
iteration explicitly does not cover.
