# DATASET_CARD.md — Phase 14

Status: 2026-08-14. 9 items, `research/dataset/items.jsonl`, verified
directly against the raw file for this card (not copied from a prior
summary).

## Motivation

Curated to give TruthLens a first, real evaluation against ground truth
this project's own author never labeled — the specific gap Section VII's
headline finding and every result after it depends on. Not built to
demonstrate a specific accuracy number; items were selected before any
TruthLens run against them (Section~V's held-out discipline).

## Composition

| Field | Value |
|---|---|
| Total items | 9 (target was 20–30; not reached, reported as a pilot-scale study, not disguised as a larger one) |
| Ground truth | TRUE: 1, FALSE: 7, MISLEADING: 1 |
| Claim type | provenance: 5, visual: 1, event: 1, misleading\_context: 1, quote: 1 |
| Political actor | BJP: 3, Karni Sena: 1, CJP: 1, Delhi Police (government): 1, Congress: 1, none (disaster misinfo): 1, AAP: 1 |
| Language | en: 7, hi (spoken): 1, hi-en-mixed: 1 |
| Modality | video: 8, photo: 1 |
| Ground-truth tier | Tier 1 (professional fact-check) for all 9 — no Tier-2 (single-annotator) item in the frozen set |
| Usable for full-pipeline evaluation | 6 of 9 (item-0003 never ingestible; items 0008/0009 have no complete real full-TruthLens run, blocked by Gemini quota) |

## Collection process

Search professional Indian fact-checking outlets (BOOM Live, Alt News,
Factly, PIB Fact Check, Reuters Fact Check, AFP Fact Check) for articles
that demonstrably embed a still-live Instagram post — not a similar claim
elsewhere. Measured hit rate: $\sim$8% (2 of the first 26 articles
checked yielded a usable item). Every accepted item's content hash is
checked against already-ingested development data and excluded on any
match. Full per-attempt log, hits and misses both:
`research/dataset/SOURCING_LOG.md`.

## Inclusion / exclusion criteria

**Included**: the professional fact-checking organization's article must
demonstrably reference or embed this specific Instagram post (not a
similar claim on a different post). The post must have been live and
fetchable at the time of inclusion.

**Excluded, with a real, logged reason each time**: articles with no
Instagram embed at all (predominantly a real, plausible property of
which claim types concentrate on Instagram vs.\ X/WhatsApp/Facebook for
this domain — `statistic`, `law\_policy`, and `historical` claim types
specifically, per two independent sourcing passes); posts that returned
HTTP 200 but with no Open Graph metadata (functionally gone, despite a
live URL); content predating this project's 2026 window; content already
used during development (checked via content hash).

## Known biases, disclosed rather than corrected for

- **FALSE-verdict skew (7/9)**: professional fact-checkers publish far
  more debunks than confirmations; this is a property of Tier-1 sourcing
  generally, not a design choice by this project. Only item-0004 is
  TRUE — the dataset cannot yet measure whether the system correctly
  clears an accurate claim at any real statistical power.
- **provenance-claim skew (5/9)**: consistent with the cross-post
  attribution problem this paper documents (Section X) as a structural
  property of how Tier-1 items get sourced, not a sampling artifact this
  project introduced.
- **Single-country, single-platform, mixed-but-English-majority
  language**: all content is Indian political short-form video on
  Instagram specifically; source-tiering domain lists and
  research-planning prompts are not tested against other national
  contexts or platforms.
- **No matched political-actor pairs**: BJP has the most items (3), but
  none are topic/structure/difficulty-matched against another single
  actor — the direct reason RQ5 (bias) is deferred rather than forced
  (Section XI).
- **Editorial/survivorship bias inherent to the sourcing method**: only
  claims a professional fact-checker chose to cover, and whose original
  post was still live at collection time, can enter this dataset. Claims
  professional fact-checkers did not cover, or whose posts were taken
  down before this project could reach them, are systematically absent
  and unmeasurable from within this dataset.
- **Ground-truth-source bias is not audited**: BOOM Live, Alt News, and
  Factly's own editorial judgment is trusted as ground truth without an
  independent check against a second fact-checking organization (Section
  XIII of the paper names this explicitly).

## Per-item summary

| ID | GT | Source org | Actor | Claim type | Language | Usable end-to-end? |
|---|---|---|---|---|---|---|
| item-0001 | FALSE | BOOM Live | BJP | provenance | en | Yes |
| item-0002 | FALSE | Alt News | Karni Sena | provenance (visual) | en | Yes |
| item-0003 | FALSE | BOOM Live | CJP | visual (AI-generated) | en | **No** — never ingestible (3 attempts) |
| item-0004 | TRUE | BOOM Live | Delhi Police (govt) | provenance | en | Yes |
| item-0005 | MISLEADING | Factly | Congress | provenance | en | Yes |
| item-0006 | FALSE | BOOM Live | none (disaster misinfo) | event (visual) | en | Yes (zero verifiable claims extracted — a real result, not a failure) |
| item-0007 | FALSE | Alt News | BJP | misleading\_context | hi (spoken) | Yes (same as item-0006) |
| item-0008 | FALSE | Alt News | AAP | quote | hi-en-mixed | **Partial** — real claims extracted, no complete verdict (Gemini quota) |
| item-0009 | FALSE | Alt News | BJP | provenance | en | **No** — no extraction ever completed |

## Intended use

Held-out evaluation of TruthLens and directly comparable baselines only.
Not intended, at this size, to support any claim about political
misinformation prevalence, partisan asymmetry, or generalization beyond
Indian Instagram political content circa 2026. Scaling past $n=9$
(Section~\ref{sec:futurework} of the paper) is the single most direct way
to extend its intended use.
