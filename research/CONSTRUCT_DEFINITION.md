# Phase 3: Redefining the Core Construct — from "Trustworthiness" to "Support Validity"

## The problem with "trustworthiness"

The Day 9 paper uses "trustworthiness" as its central contrastive
construct against "label accuracy," built around one real finding: two
general validator fixes improved something (recall against human
-judged-unsupported outputs, 16.7%→40%) without moving reel-level bucket
accuracy at all. But "trustworthiness" itself is never formally defined
anywhere in the paper — not in the Architecture section, not in the
Discussion, not in the Conclusion where it does the most rhetorical work.
A skeptical reviewer's question is exact and fair: **trustworthy according
to what measurement?**

## What is actually being measured

Two genuinely distinct things are currently folded into one word:

1. **A deterministic, code-checkable property** of a verdict's own stated
   output: do its citations exist, were their sources fetched, do its
   numbers appear in cited text, does its label agree with its own
   reasoning. This is exactly and only what `validate_verdict()`'s four
   checks compute. It requires no human judgment and is fully auditable.
2. **A human-judged, holistic quantity**: whether a reviewer reading the
   verdict's full reasoning would call it unsupported or unreliable. This
   is broader than (1) — it can also fail from things (1) structurally
   cannot see (wrong-entity evidence treated as relevant, vague reasoning
   that clears a word-count bar but says nothing specific).

The paper's real finding is that improving (1) improves the *validator's
own recall against* (2) — not that (1) and (2) are the same thing, and
not that either one is "trustworthiness" in the everyday sense (which
would also implicate calibration, presentation, user perception — none
of which this paper measures or claims to).

## Proposed replacement construct: Support Validity

**Definition.** A verdict has **support validity** to the extent that
every specific, checkable factual assertion embedded in it — its cited
evidence IDs, the sources those citations point to, the numbers stated in
its reasoning, and the logical relationship between its stated reasoning
and its chosen label — can be verified against data already present in
the pipeline's own evidence matrix, without invoking a second, equally
fallible model judgment.

**Operationalization** (exactly `validate_verdict()`'s four checks, no
more, no less):
1. Citation existence
2. Source-fetch existence
3. Numeric grounding
4. Label/reasoning consistency

**Explicitly out of scope for this construct** (each already measured,
if at all, by a different mechanism elsewhere in the paper, and must not
be implied as part of "support validity"):
- Evidence-to-claim topical relevance — RQ4's job (source-tiering /
  four-way evidence metric), not the validator's.
- Evidence-to-reasoning stance correctness (did `evidence_analysis`
  correctly judge supports/contradicts/irrelevant) — currently
  human-audited only, not deterministically checked at all (a real,
  named gap — see `docs/SYSTEM_AUDIT.md` §5.3, and the motivation for
  Phase 5's entity-consistency validator).
- Entity consistency — not yet implemented (Phase 5 target).
- Label accuracy against ground truth — a completely separate axis,
  already correctly distinguished in the paper's central finding.
- General "hallucination" in any broader sense — a verdict can have
  perfect support validity by this definition and still be wrong, if the
  model correctly cited and correctly quoted evidence that it
  nonetheless misinterpreted, or if retrieval never found the right
  evidence in the first place.

## What changes in the paper

- Every load-bearing use of "trustworthiness" (Abstract, Introduction,
  Section IX, Discussion, Conclusion) is replaced with "support validity"
  once formally introduced, with one explicit definition paragraph placed
  in Section IV (architecture/validation subsection) the first time the
  term is used, exactly as done here.
- The central finding is restated precisely: *"Two general fixes
  improved the deterministic validator's recall against human-judged
  unsupported output from 16.7% to 40%, without moving reel-level label
  accuracy — demonstrating that support validity, as operationalized by
  these four checks, is separable from label accuracy: a system can
  become more effective at correctly identifying its own unsupported
  outputs without its label-level correctness rate changing."*
- No claim is made that support validity measures trustworthiness in
  general, user trust, calibration, or hallucination broadly. This
  boundary is stated explicitly, not left implicit.

Status: definition finalized this pass. Applied to the paper during the
terminology/restructure pass (Phase 19/21), after the baseline-fix
results (Finding 1) are in, so both changes land together rather than in
fragmented edits.
