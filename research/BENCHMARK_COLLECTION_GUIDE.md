# BENCHMARK_COLLECTION_GUIDE.md

Status: 2026-08-14. `research/RESEARCH_ROADMAP_V2.md` Phase 1 tooling —
governing brief Step 5. This document explains how to use
`backend/research/benchmark_v2/candidate_tracker.py` to work through
benchmark sourcing efficiently. **It does not itself collect anything.**
No candidates are pre-populated by this pass — per the brief's explicit
Step 8 ("do not jump directly into collecting dozens of benchmark
items"), this is infrastructure only.

## Why a tracker, not just adding straight to `items.jsonl`

`DATASET_CARD.md` already measured the real constraint: roughly 8% of
professional fact-check articles checked (2 of the first 26) yield a
usable item — a still-live post the article demonstrably embeds. That
means for every item that becomes real benchmark data, on the order of
12 articles get checked and rejected. Without a tracker, that rejected
majority leaves no trace: the same article can get re-checked by a
future pass, and there's no way to answer "how much sourcing effort has
actually gone into this" except by re-deriving it from memory. The
tracker exists to make that effort visible and non-repeated, not to
speed up the underlying 8% rate — nothing here changes how often a
fact-check actually embeds a live post.

## The eligibility state machine

```
DISCOVERED -> ARTICLE_FOUND -> SOCIAL_REFERENCE_FOUND -> MEDIA_RETRIEVABLE
    -> GROUND_TRUTH_VERIFIED -> ELIGIBLE
```

Plus two terminal off-ramps at any point: `REJECTED` (with
`rejection_reason` always set) and `UNRESOLVED` (real ambiguity that
needs a second opinion before a decision either way — not a synonym for
"forgot to finish").

| State | Means |
|---|---|
| `DISCOVERED` | A candidate fact-check article/claim identified, nothing else checked yet |
| `ARTICLE_FOUND` | The fact-check article itself is real and accessible |
| `SOCIAL_REFERENCE_FOUND` | The article demonstrably references or embeds a specific social post (not just "some post like this exists") |
| `MEDIA_RETRIEVABLE` | That specific post is still live and its media is actually fetchable |
| `GROUND_TRUTH_VERIFIED` | The claim and label are unambiguous from the article — no guessing at what exactly is being fact-checked |
| `ELIGIBLE` | All of the above hold — ready for a human to promote into `items_v1_as_v2_schema.jsonl`'s sibling for the growing `v2` set |
| `REJECTED` | Failed at some stage; `rejection_reason` records which and why |
| `UNRESOLVED` | Genuine ambiguity (e.g. label mapping unclear, media borderline-identifiable) needing a second reviewer |

Progression is tracked but not force-sequenced — a well-documented
article can establish several states from one read. Every transition
(including creation) is appended to the candidate's own `history` list,
never overwritten, so a candidate's full path to `ELIGIBLE` or
`REJECTED` stays auditable.

## Basic usage

```python
from research.benchmark_v2.candidate_tracker import Candidate, add_candidate, update_status, list_candidates

add_candidate(Candidate(
    candidate_id="cand-2026-08-15-001",
    factchecker="boomlive.in",
    factcheck_article="https://www.boomlive.in/fact-check/...",
))

update_status("cand-2026-08-15-001", "ARTICLE_FOUND", note="real BOOM article, dated 2026-08-10")
update_status("cand-2026-08-15-001", "SOCIAL_REFERENCE_FOUND", note="embeds instagram.com/reel/XYZ")
# ... continue through the remaining checks ...
update_status("cand-2026-08-15-001", "ELIGIBLE", note="all 7 quality rules below pass")

list_candidates("ELIGIBLE")  # everything ready for manual promotion
```

Storage: `research/dataset/candidates_v2.jsonl` (created on first use, one
JSON object per line — same format convention as `items.jsonl`, but this
file is explicitly a working/scratch artifact, not itself benchmark
ground truth).

## Quality rules before marking `ELIGIBLE` (governing brief's own list)

A candidate should satisfy all seven before promotion; if one is
missing, note it explicitly in `history` rather than silently promoting
anyway:

1. Independent fact-check source (not the project's own judgment).
2. Clearly stated claim — no ambiguity about what's being checked.
3. Independently established ground truth (the article's own verdict,
   not inferred).
4. Identifiable social media post, specific URL.
5. Reproducible media access, or a preserved research artifact if the
   post is later taken down.
6. No ambiguity in label mapping (the article's verdict maps cleanly
   onto `TRUE`/`FALSE`/`MISLEADING`/etc. — see `DATASET_SPEC.md`'s
   existing ground-truth-tier definitions).
7. Provenance recorded — which outlet, which article, when checked.

## Promotion into the real dataset

Promotion from `ELIGIBLE` to an actual new row in a `v2` benchmark file
is **manual**, deliberately: content-hash dedup against both
`items.jsonl` and the live `reels` table (per `DATASET_SPEC.md`'s
existing held-out discipline) and split assignment (dev/validation/test,
per `DATASET_SCHEMA_V2.md`) both require a real decision, not a script
default. `composition_of_eligible()` in the tracker module gives a quick
running count of label/claim-type/language among `ELIGIBLE` candidates,
useful for noticing live whether a new candidate actually closes a known
gap (e.g. this dataset's persistent shortage of `TRUE`-labeled items)
before spending more sourcing effort in a direction that wouldn't help.
