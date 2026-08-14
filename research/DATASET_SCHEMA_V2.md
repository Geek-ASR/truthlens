# DATASET_SCHEMA_V2.md

Status: 2026-08-14. Formal schema for real-content benchmark items going
forward, per `RESEARCH_ROADMAP_V2.md` Phase 1 / the governing brief's
Step 2. This document defines the schema only — it does not replace or
modify `research/dataset/items.jsonl`, which remains exactly as it was
(the `benchmark_v1` artifact, already used to produce every result in
`research_paper/main.tex`). Per the brief's own Rule 1 ("do not silently
overwrite previous benchmark versions"), v1 is retired-in-place, not
edited: `research/dataset/items_v1_as_v2_schema.jsonl` is a **new,
separate file** presenting the same 9 items' same facts under this new
schema, built by `backend/research/benchmark_v2/migrate_v1_to_v2_schema.py`
— an additive migration, not an in-place edit.

## Fields

| Field | Type | Notes |
|---|---|---|
| `item_id` | string | Unchanged from v1 (`item-0001` etc.) |
| `benchmark_version` | string | `"v1"` for the 9 already-used items; `"v2"` for anything newly collected under this schema |
| `split` | `"dev"` \| `"validation"` \| `"test"` \| `null` | See "Split assignment" below |
| `media` | string | `"video"` \| `"photo"` — renamed from v1's `modality`, which this schema reserves for *input-signal* modality instead (see `audio_available` etc.) |
| `media_hash` | string \| null | `media_content_hash` from the live `reels` row when ingested, else null |
| `platform` | string | `"instagram"` today; the field exists so a future YouTube Shorts/TikTok item doesn't need a schema change |
| `original_url` | string | The social post itself (v1's `source_url`) |
| `factcheck_url` | string | Renamed from v1's `ground_truth_source_url` |
| `factchecker` | string | Extracted from v1's `labeler` field (`"tier-1-source:boomlive.in"` → `"boomlive.in"`) |
| `publication_date` | string \| null | The post's own date (v1's `date`) |
| `factcheck_date` | string \| null | Not tracked in v1 — null for all 9 v1 items, populated going forward |
| `ground_truth_label` | string | Unchanged (`TRUE`/`FALSE`/`MISLEADING`/etc.) |
| `ground_truth_claim` | string | Renamed from v1's `claim_text` |
| `claim_type` | string | Unchanged — this is the dataset's own claim-type vocabulary, deliberately distinct from `ClaimType` in `app/db/models.py` (see `DATASET_SPEC.md`'s existing explanation, still accurate) |
| `political_actor` | string | Unchanged |
| `language` | string | Unchanged |
| `audio_available` | bool \| null | Whether the ingested reel has a non-empty transcript. Derived from the live `reels` row for all 9 v1 items (real data, queried directly — not guessed); null only for item-0003, never ingested |
| `ocr_available` | bool \| null | Whether the ingested reel has non-empty OCR text. Same provenance as above |
| `caption_available` | bool \| null | Whether the post has caption text. Same provenance |
| `visual_information_available` | bool \| null | Whether vision-context analysis produced output. Same provenance |
| `cross_post_possible` | bool \| null | Whether this item's structure allows the cross-post attribution problem (`main.tex` Section X) to apply at all — true for every video/photo item |
| `cross_post_verified` | bool \| `"partial"` \| null | Whether a human reviewer actually confirmed the checkworthy claim lives outside this specific post's own content. Populated only for the 6 items `MULTIMODAL_EVALUATION.md` actually evaluated for this (item-0001/0002/0005/0006 = `true`; item-0004 = `false`; item-0007 = `"partial"`, per that document's own hedge); `null` for item-0003/0008/0009, which were never evaluated for this — not silently defaulted to `false` |
| `difficulty` | string \| null | Not yet a real, defined rating anywhere in this project — `null` for every v1 item rather than an invented placeholder. A genuine open item for whoever defines a difficulty rubric under Phase 1 (below) |
| `development_split` | bool | Unchanged from v1's implicit meaning: `true` for every item in this held-out set (none are development-only content) |

## Split assignment for `benchmark_version: "v1"`

All 9 v1 items are assigned `split: "dev"`, **not** `"test"`, even though
the paper describes them as "held out." This is a deliberate,
documented methodological decision, not an oversight:

The `RESEARCH_ROADMAP_V2.md`/governing-brief TEST-set discipline (Step 3)
requires that a TEST item never inform a prompt, threshold, model, or
validator change. The v1 9 items do not meet that bar retroactively —
they were used to produce the paired baseline comparison, and the
resulting headline finding directly motivated two general validator
fixes (`main.tex` Section IX) that were then re-scored against the
*same* 9-claim sample. That is legitimate, disclosed, ground-truth
-independent iteration under the old (pre-V2) protocol, but it is
exactly the kind of exposure that disqualifies an item from being called
TEST under the new, stricter discipline. Calling them TEST now would be
a retroactive relabeling that oversells their evidentiary status — the
same category of error this whole program exists to catch.

**Practical consequence**: Phase 1's benchmark expansion
(`RESEARCH_ROADMAP_V2.md` Phase 1) must source enough new `v2` items to
populate genuine `validation` and `test` splits from birth — the v1 set
alone cannot retroactively supply a clean TEST set no matter how it's
relabeled.

## What's NOT done as part of this schema definition

Populating `benchmark_version: "v2"` items — i.e., collecting new
benchmark content — is explicitly out of scope for this pass (governing
brief Step 8: "do not jump directly into collecting dozens of benchmark
items"). This document and its migration script establish the schema and
migrate the *existing* 9 items into it; `BENCHMARK_COLLECTION_GUIDE.md`
covers the tooling for actually growing the set.
