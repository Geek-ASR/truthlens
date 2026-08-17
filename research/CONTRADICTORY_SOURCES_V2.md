# CONTRADICTORY_SOURCES_V2.md — Phase 11 (Step 18 category #8)

Status: 2026-08-18. `research/RESEARCH_ROADMAP_V2.md` Phase 11's
20-category adversarial list includes "contradictory sources" (#8) —
not covered by this session's other adversarial work (EXP-019/020/026
covered entity/temporal mismatch, claim-extraction robustness, and
prompt injection, all upstream of or within the validator; none tested
how `verdict.propose_verdict()` itself resolves a claim where multiple
credible-looking sources genuinely disagree).

## Method

`backend/research/adversarial_v2/run_contradictory_sources_stress.py`:
3 synthetic-but-realistic cases, each a constructed `Claim` with 2-4
constructed `Evidence`/`Source` rows carrying real reliability scores
and stances, run through the real, unmodified `verdict.propose_verdict()`
(which internally runs the real `validate_verdict()`, Checks 1-7).
Unpersisted/rolled back, per this session's research-script default.

1. **direct_conflict_equal_reliability**: two similarly-reliable sources
   (0.85 government, 0.80 news) flatly disagree on a death toll (47 vs
   52).
2. **reliability_weighted_conflict**: a 0.95-reliability primary
   -government source supports the claim; a 0.20-reliability, uncited
   anonymous blog contradicts it. The reliability gap is explicit in
   the evidence matrix text the model receives.
3. **majority_with_credible_outlier**: 3 established-news sources
   (0.75 each) agree on a protest headcount; 1 higher-reliability
   news-wire source (0.85) disagrees with an independent aerial-photo
   estimate.

## Finding: a real, reproducible reliability-weighting failure

Case 2's initial run: `verdict=MOSTLY_FALSE, confidence=0.0`. Re-running
the identical evidence 6 more times (n=7 total, pre-fix,
`verdict.v2`) produced: `MOSTLY_FALSE` ×3, `UNVERIFIED` ×3, `OUTDATED`
×1 (confidence 0.0 in most runs, but 1.0 once, paired with the
`OUTDATED` label — a wrong label delivered with *maximum* stated
confidence).

**0 of 7 runs produced TRUE or MOSTLY_TRUE**, despite the higher
-reliability source (0.95, primary government, directly quoted)
supporting the claim and the contradicting source being an anonymous,
uncited blog (0.20 reliability) whose own explanation the model's
reasoning correctly identifies as unreliable in prose — e.g. one run's
`reasoning_summary` states verbatim: *"TaxGossipBlog provides a
contradictory claim without any official notification or credible
sources to back it up"* — and still resolves to a non-TRUE label. The
model's own stated reasoning and its chosen verdict label disagree,
structurally similar in shape to `research/FAILURE_TAXONOMY.md` #19
("a label confidently contradicting the model's own stated reasoning"),
though a distinct case: #19 is about "no evidence found" language paired
with a confident label; this is about *correctly assessing* the
reliability imbalance in prose while still failing to let that
assessment steer the categorical verdict.

`VERDICT_SYSTEM_PROMPT` (pre-fix, `verdict.v2`) told the model to use
source quality when setting **confidence**, but gave no explicit
instruction for how conflicting sources of *different* reliability
should affect the **verdict label** itself — a plausible root cause:
the model appears to treat "some contradiction exists" as sufficient to
avoid a confident positive label, regardless of which side the
reliability evidence favors.

## Attempted fix: prompt hardening (verdict.v2 → verdict.v3) — measured, found insufficient

Added an explicit rule to `VERDICT_SYSTEM_PROMPT`: conflicting sources
of asymmetric reliability should not by default drag the verdict to
UNVERIFIED/MOSTLY_FALSE; the higher-reliability, more direct source
should carry more weight in the *label*, not just the confidence score;
reserve UNVERIFIED/MISLEADING for genuinely comparable-reliability
conflicts. Included a worked example structurally similar to, but not
identical to (a national statistics agency vs. an anonymous social
-media comment), the held-out test case.

**Re-running the same reliability_weighted_conflict case 7 more times
post-fix: still 0/7 TRUE or MOSTLY_TRUE** (5 `UNVERIFIED`, 2
`MOSTLY_FALSE`, all confidence 0.0). The prompt-level fix **did not
achieve its goal**. One arguably-positive side effect, not claimed as
statistically established at n=7: the dangerous "wrong label, maximum
confidence" outlier (`OUTDATED`/1.0) that appeared once pre-fix did not
recur post-fix — but a single pre-fix occurrence is not strong enough
evidence to credit the prompt change specifically.

A sanity check on case 3 (`majority_with_credible_outlier`, which had
resolved cleanly to `MOSTLY_TRUE`/0.8 on its one pre-fix run) shows the
same underlying instability, not a clean regression: 4 post-fix reruns
produced `MOSTLY_TRUE`/0.8 twice and `UNVERIFIED`/0.4 twice. Since case
3 was only sampled once pre-fix, there isn't enough pre-fix data to
call this a regression versus pre-existing noise the single early
sample happened not to show.

**Conclusion, stated plainly**: verdict-label selection under genuinely
conflicting evidence shows substantial run-to-run instability for
llama3.2, both before and after this prompt change. The specific,
targeted failure (an uncited low-reliability source preventing a
confident TRUE verdict against a high-reliability primary source) was
**not resolved** by prompt engineering alone — the third time this
session prompt-only fixes have proven insufficient for a small local
model's behavior (after EXP-021's `source_quote` attempt and, more
mildly, EXP-026's prompt-injection hardening, which *did* measurably
help but was explicitly not claimed to reach 0% failure at scale
either). The `verdict.v3` prompt change is kept — it is objectively
correct guidance, adds no code complexity, and is not shown to make
anything worse — but is **not represented as a fix**. The right next
step is very likely a deterministic validator check (mirroring how
Checks 6/7 succeeded where prompt-only approaches for entity/temporal
consistency would not have been trustworthy either): compare each cited
evidence item's `reliability_score` against the verdict label's
direction and flag/downgrade cases where a low-reliability, indirect,
or uncited source appears to have out-weighted a high-reliability,
direct, primary one. Not built this pass — this is a new capability
requiring its own precedent-setting integration decision (Rule 4: no
complexity without experimental justification), not a same-pass
addition.

## A partial, existing mitigation already in place

Several of the unstable runs were independently caught and downgraded
by the *existing* deterministic validator (`validation_status:
downgraded_missing_citation`, `downgraded_unsupported_stat`) rather
than passing straight through as `passed`. This doesn't fix the
underlying label instability, but it means at least some of these cases
already don't reach a human reviewer or a publish decision with a
false, unqualified "passed" status — a real, if partial and
uncharacterized-at-scale, safety net already in place before this pass.

## What changed in production

- `backend/app/services/ai/prompts.py`: `VERDICT_SYSTEM_PROMPT` gained
  an explicit reliability-weighting rule; version bumped `verdict.v2`
  → `verdict.v3`. Kept despite not resolving the target failure, per
  the reasoning above.

## Follow-up (EXP-030): the named deterministic check, built and integrated

The "likely real fix" named above — a deterministic validator check
comparing cited-evidence reliability against verdict direction — was
built as a candidate
(`backend/research/verdict_reliability_v2/reliability_direction_check.py`)
and evaluated before any integration decision, per this project's own
Rule 4 discipline and the same pattern Checks 6/7 were held to:

- **10 hand-designed synthetic cases** (ground-truth precision/recall,
  including edge cases: no conflict, a close reliability gap that
  should NOT fire, missing reliability data, multiple evidence items
  per side): **10/10 correct**.
- **A replay of this document's own 19 real observed verdict labels**
  (14 `reliability_weighted_conflict` trials across both prompt
  versions, 5 `majority_with_credible_outlier` trials): **14/14 real
  wrong trials would have been caught** (this required adding
  `OUTDATED` to the checked negative-label set — the one real trial
  that paired a wrong label with maximum confidence used it, and it
  wasn't originally covered), and **0/5 false positives** on the
  genuinely closer-call sanity-check trials (0.10 reliability gap,
  below the 0.4 threshold).
- **The existing 34-case adversarial benchmark** (`build_and_run_v2.py`):
  **0 interactions** — none of those cases wire real
  `Evidence.stance` + `Source.reliability_score` together for cited
  evidence, confirming zero regression risk before integration, not
  just assuming it.

Integrated as **Check 8** (`app/pipeline/validation.py`,
`ValidationStatus.downgraded_reliability_mismatch`, migration
`403a421884b7`), with 8 new regression tests in `tests/test_validation.py`
covering the true-positive shape, its mirror image, the `OUTDATED`
edge case, a correctly-resolved control, the close-gap non-fire case,
the single-stance non-fire case, and the plain-`object()`
backward-compatibility guarantee. Re-ran the full 34-case benchmark
through the real, now-updated `validate_verdict()` after integration:
precision/recall unchanged (87.5%/60.9%, identical to pre-integration),
confirming the zero-regression prediction empirically, not just in
theory. This directly closes `research/FAILURE_TAXONOMY.md` #24.

## Raw data

`research/results/contradictory_sources_stress_20260818.json` (3-case
initial run, pre-fix). The n=7 pre/post-fix batches and the
majority-outlier sanity check were run inline (not written to a
separate results file) — exact verdict/confidence sequences are quoted
above and in `experiments/registry.jsonl`'s EXP-029 entry. Generator:
`backend/research/adversarial_v2/run_contradictory_sources_stress.py`.
