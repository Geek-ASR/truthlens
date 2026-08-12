# Ground Truth Status

## Current dataset: 7 items, all Tier 1

| ID | Verdict | Source org | Political actor | Claim type | Language |
|---|---|---|---|---|---|
| item-0001 | FALSE | BOOM Live | BJP | provenance | en |
| item-0002 | FALSE | Alt News | Karni Sena | provenance (visual) | en |
| item-0003 | FALSE | BOOM Live | CJP | visual (AI-generated) | en |
| item-0004 | TRUE | BOOM Live | Delhi Police (govt) | provenance | en |
| item-0005 | MISLEADING | Factly | Congress | provenance | en |
| item-0006 | FALSE | BOOM Live (Hindi) | none (disaster misinfo) | event (visual, AI-generated) | en caption |
| item-0007 | FALSE | Alt News (Hindi) | BJP | misleading_context | hi (spoken) |

Every label above is the independent professional organization's own
published verdict (see `ANNOTATION_GUIDELINES.md` Task A, Tier 1) — not
a judgment made by this project, by Aditya, or by any AI involved in
this project. This is the entire methodological point of Tier 1: the
system being evaluated (and the people building it) never touch the
labeling process for these items.

## Inter-annotator agreement: not applicable yet, stated honestly

**No IAA statistic is computed or reported, and none will be fabricated
to fill this section.** Here is exactly why, so this isn't mistaken for
an oversight:

- Tier-1 ground truth doesn't have an "annotator" in the IAA sense at
  all — the label is a single organization's single published verdict.
  Computing "agreement" would require either (a) a second independent
  professional fact-check of the *same* post (not generally available —
  these organizations don't duplicate each other's specific-post
  coverage), or (b) introducing a human annotator from this project to
  re-judge Tier-1 items, which would defeat the purpose of using
  independent ground truth in the first place.
- Tier-2 items (single-annotator or multi-annotator, per
  `ANNOTATION_GUIDELINES.md`) are where IAA becomes meaningful, and none
  exist in the dataset yet.
- Per `EXPERIMENT_PLAN.md` §7.2: if Tier-2 items are added and only one
  annotator (Aditya) is available, this section will say exactly that —
  "single-annotator ground truth, no IAA computed" — rather than a
  Cohen's/Fleiss' kappa number with no real second rater behind it.

## What would change this section

1. Aditya (or a second recruited annotator) independently labels a
   sample of Tier-2 items → Cohen's kappa computed on that sample,
   reported here with the exact item count it was computed from.
2. Task B (atomic-claim annotation, `ANNOTATION_GUIDELINES.md`) is
   inherently a task this project's own people must do, even for Tier-1
   items — the professional fact-checker's verdict covers the headline
   claim, not a full atomic decomposition. If Task B is done by more
   than one person for any item, that overlap's agreement rate belongs
   here too.

## Dataset composition gaps (from `dataset/SOURCING_LOG.md`, restated here for visibility)

- 4 of 7 items are `provenance`-type claims; `statistic`, `quote`,
  `law_policy`, `historical`, and `true_claim` remain entirely
  unrepresented. Pass 2's sourcing log records a real (not yet
  confirmed as structural) difficulty finding statistic-type claims
  with a specific Instagram embed, as opposed to WhatsApp/X.
- 6 of 7 items are FALSE-verdict — a possible structural property of
  Tier-1 sourcing (professional fact-checkers publish far more debunks
  than confirmations), flagged in `SOURCING_LOG.md` as worth stating in
  the paper's own dataset-construction discussion, not just as a gap to
  keep chasing.
- 1 of 7 items (item-0007) has confirmed Hindi spoken content — real
  progress from pass 1's all-English set, though a genuinely
  code-switched (Hindi+English within the same transcript) item, the
  project's actual stated target domain, is still not represented.
- n=7 is too small for any of RQ3/RQ5/RQ6 to produce a statistically
  meaningful result as-is; `EXPERIMENT_PLAN.md` already treats these as
  conditional/small-sample for exactly this reason.
