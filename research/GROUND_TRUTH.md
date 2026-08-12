# Ground Truth Status

## Current dataset: 5 items, all Tier 1

| ID | Verdict | Source org | Political actor | Claim type |
|---|---|---|---|---|
| item-0001 | FALSE | BOOM Live | BJP | provenance |
| item-0002 | FALSE | Alt News | Karni Sena | provenance (visual) |
| item-0003 | FALSE | BOOM Live | CJP | visual (AI-generated) |
| item-0004 | TRUE | BOOM Live | Delhi Police (govt) | provenance |
| item-0005 | MISLEADING | Factly | Congress | provenance |

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

- All 5 items are provenance/visual-type claims — no statistic, quote,
  law/policy, or historical-fact claim type yet.
- All 5 items are English-language — no Hindi/Urdu-mixed transcript item
  yet, despite that being a stated target and a real part of the
  system's deployment domain.
- n=5 is too small for any of RQ3/RQ5/RQ6 to produce a statistically
  meaningful result as-is; `EXPERIMENT_PLAN.md` already treats these as
  conditional/small-sample for exactly this reason.
