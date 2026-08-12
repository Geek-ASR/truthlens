# Annotation Guidelines

Governs two distinct annotation tasks that must not be conflated:
(A) **item-level ground truth** (was the post's claim true/false/misleading)
and (B) **atomic-claim-level annotation** (breaking a post into the
individual checkable assertions it makes, needed for Claim Coverage/
Recall in `METRICS.md` §2). An item can have solid Tier-1 ground truth
for (A) while (B) still requires human work, since no professional
fact-checker publishes an atomic-claim decomposition — they publish a
verdict on the headline claim.

## Task A — item-level ground truth

**Tier 1 (preferred, used for all 5 items so far):** the label is the
independent professional fact-checking organization's own published
verdict, mapped onto TruthLens's `VerdictLabel` vocabulary by the
following fixed rule (applied mechanically, not by the annotator's own
judgment, so this step introduces no new subjectivity):

| Org's own wording (observed so far) | Mapped label |
|---|---|
| "False" / "Fake" | `FALSE` |
| "Misleading" | `MISLEADING` |
| "True" / "confirmed authentic" (with an explicit unconfirmed-caveat) | `TRUE`, with the caveat excluded from `claim_text` scope (see item-0004's own notes for a worked example) |
| "Partly true" / "Mixed" (not yet observed, but anticipated) | `MOSTLY_TRUE` or `MOSTLY_FALSE`, decided by which direction the org's own summary leans, recorded in `ground_truth_notes` |

No annotator "double-checks" or overrides a Tier-1 professional verdict
based on their own reading of the evidence — that would quietly convert
Tier-1 ground truth into Tier-2 (self-labeled) while still claiming
Tier-1's methodological credibility. If an annotator disagrees with a
professional fact-checker's conclusion, that disagreement is recorded as
a note, and the item is flagged for exclusion or re-classification as
Tier-2 — never silently relabeled.

**Tier 2 (fallback, not yet used):** human-labeled directly from primary
sources, following the same `VerdictLabel` vocabulary. Requires:
1. The labeler works from primary sources only (not from TruthLens's own
   output, not from another AI's summary of the claim).
2. A second, independent labeler, working blind to the first labeler's
   conclusion, for at least a subset of Tier-2 items — this is what
   makes inter-annotator agreement (`GROUND_TRUTH.md`) computable at
   all. Per `EXPERIMENT_PLAN.md` §7.2, if no second labeler is available,
   `GROUND_TRUTH.md` states this plainly rather than reporting a
   fabricated or single-rater-only "agreement" number.

## Task B — atomic claim annotation (for Claim Coverage, `METRICS.md` §2)

For each dataset item, before running it through any TruthLens
configuration:
1. Watch/read the post's full content (video+audio+on-screen
   text+caption, or photo+caption).
2. List every **checkworthy** assertion it makes or clearly implies —
   the same "atomic, independently-checkable claim" standard
   `CLAIM_EXTRACTION_SYSTEM_PROMPT` already uses (see
   `backend/app/services/ai/prompts.py`), applied by a human instead of
   the model, so the two are directly comparable.
3. For each claim, label:
   - `claim_text` — precisely worded, human's own words.
   - `factual` / `opinion` / `prediction` / `satire` / `rhetorical` —
     same `ClaimType` vocabulary as the system, so extracted-vs-ground
     -truth comparison isn't fighting a vocabulary mismatch.
   - `modality` — is this claim's evidence primarily in the transcript,
     the on-screen text/graphics, or only visible in the video/image
     itself with no textual trace at all (this last category is exactly
     what `is_visual_claim`/`is_provenance_claim` in `items.jsonl` flag,
     and is the crux of RQ3).
   - `veracity` — filled in only for claims covered by the item's Task A
     ground truth; left blank for claims the professional fact-check
     didn't address (a post can make several claims but only one gets
     professionally verdicted).
   - `evidence` — for Tier-1 items, a pointer to the relevant part of
     the fact-checker's own article; for Tier-2, the primary source the
     labeler used.
   - `provenance_relevance` — does this specific claim concern *what the
     footage genuinely shows* (provenance) as opposed to a separate
     factual assertion made *in* the footage (e.g., a spoken statistic)?
   - `ambiguity` — free-text note when a claim is genuinely hard to
     pin down as one atomic assertion; these cases are flagged, not
     silently resolved by picking whichever phrasing is more convenient.

Output: `research/annotations/atomic_claims_{item_id}.json`, one file
per dataset item, schema matching the fields above.

## Cross-cutting rules

- No annotation (Task A or B) is ever performed by an LLM and presented
  as ground truth, per Rule 2/Rule 3. An LLM (including this project's
  own Claude-based tooling) may assist by drafting a *candidate* list of
  claims for a human to review/edit/reject — the human's adjudicated
  output is what's recorded, never the draft as-is. Every such
  LLM-assisted draft is marked `llm_assisted_draft: true` in the
  annotation file's metadata so this is auditable, not hidden.
- Annotation happens **before** an item's TruthLens output is looked at,
  for exactly the items where that's practical (Task A already satisfies
  this by construction for Tier-1 items, since the professional
  fact-check predates this project's involvement entirely). Task B
  (atomic claims) must also be done blind to TruthLens's own extracted
  claims — an annotator who has already seen what TruthLens extracted
  cannot un-see it, so the order of operations is: annotate first, run
  the system second, compare third.
