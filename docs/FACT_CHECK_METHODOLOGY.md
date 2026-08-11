# TruthLens — Fact-Check Methodology

This document is the editorial/methodological counterpart to
ARCHITECTURE.md. It is written to also be publishable, in adapted form,
on the public `truthlens.example/methodology` page — operators should be
able to defend every step here to a skeptical reader.

## Core principle

```
Reliable evidence → Analysis → Verdict
```

never

```
Desired verdict → Find evidence
```

The system has no concept of a "target" party, politician, or ideology
anywhere in its data model or prompts. The same pipeline, the same source
tiers, and the same verdict categories apply regardless of who is named in
a claim.

## 1. What gets fact-checked

Not every sentence in a reel is a fact-check candidate. Claim extraction
(product spec §10-11) tags every extracted statement as one of:

- **Factual** — a statement about a verifiable state of the world
  ("Government X increased tax Y by 10%"). Eligible for research.
- **Opinion** — a value judgement ("Government X is terrible"). Not
  fact-checked; may be noted as context but never assigned TRUE/FALSE.
- **Prediction** — a claim about the future ("This policy will destroy the
  economy"). Never assigned TRUE/FALSE; may be labeled `UNVERIFIED` with
  an explanation of why predictions aren't verifiable, or skipped
  entirely if not editorially significant.
- **Satire** — flagged for human review rather than auto-processed as if
  literal.
- **Rhetorical** — not a factual assertion; skipped.

Only `factual` claims marked `verifiable: true` proceed to research.

## 2. Source tiers (product spec §12) and how they're used

1. **Tier 1 — Primary sources**: government sites, official documents,
   parliamentary/court records, election commissions, official
   statistics, laws/regulations, original research/datasets, company
   filings. Highest weight in scoring.
2. **Tier 2 — Highly credible secondary sources**: wire services (Reuters,
   AP), major broadcasters/newspapers with established editorial
   standards, established academic institutions.
3. **Tier 3 — Specialized fact-checking organizations**: Snopes,
   PolitiFact, FactCheck.org, AFP Fact Check, Reuters Fact Check, BOOM,
   Alt News, India Today Fact Check, The Quint WebQoof, and comparable
   regional outlets.

Tiers set a **prior**, not a verdict. A Tier 1 government press release
can still be contradicted by Tier 1 official statistics; a Tier 3
fact-check org can be outdated. The system always records and can display
disagreement rather than silently picking the "best" source (see §6).

## 3. Source reliability score (product spec §13)

Each retrieved source gets a `reliability_score` (0-1) computed from named
sub-dimensions (stored in `sources.reliability_breakdown`, never a single
opaque number):

| dimension | question it answers |
|---|---|
| primary-source status | is this the origin of the information, or reporting on it? |
| author identity | is a named, identifiable author/institution attached? |
| publication reputation | tier classification above, plus known corrections record |
| evidence transparency | does the source itself cite verifiable underlying data? |
| recency | how close is publication to the event and to now? |
| directness | does it address this specific claim, or something adjacent? |
| corroboration | do independent sources agree? |
| conflict of interest | does the source have a stake in the claim's outcome? |

The score is a deterministic weighted combination of dimensions that are
themselves partly rule-based (tier, recency by date arithmetic) and
partly LLM-assessed (transparency, directness, conflict) — the LLM never
assigns the *final* number directly; it assigns the qualitative
sub-judgments that feed a fixed formula. This keeps scoring auditable and
prevents the model from being able to rationalize an inflated score to
justify a verdict it "wants."

Sources are never trusted purely because they appear on a pre-defined
tier list (§12 "do not blindly trust"): a Tier 1 or Tier 3 source with a
low transparency/directness/corroboration score for *this specific claim*
still scores low overall.

## 4. Evidence matrix (product spec §14)

For every claim, each retrieved, actually-fetched source becomes one row
in the `evidence` table with a `stance` (`supports` / `contradicts` /
`provides_context` / `irrelevant`) and a short structured `explanation`.
This matrix — not a single model's summary — is what the verdict stage
reads. It is retained permanently and is what a correction review starts
from.

## 5. Verdict categories (product spec §5) and when each applies

| Verdict | When to use |
|---|---|
| TRUE | Evidence clearly supports the claim as stated, with no material missing context |
| MOSTLY TRUE | Central claim supported; some qualification/context is missing but doesn't change the substance |
| MISLEADING | Contains real elements but creates a materially false overall impression |
| MOSTLY FALSE | A kernel of truth, but the overall statement is substantially wrong |
| FALSE | Reliable evidence directly contradicts the claim |
| UNVERIFIED | Insufficient reliable evidence either way — this is a legitimate, frequently-correct output, not a failure state |
| OUTDATED | Was accurate once, no longer is |
| MISSING CONTEXT | Technically true in isolation, but misleading without added context |

Binary TRUE/FALSE is never forced onto a claim the evidence doesn't
support that cleanly (product spec §37). `UNVERIFIED` is the required
output — not a best guess — when evidence is ambiguous or thin.

## 6. Confidence score (product spec §19)

Internal `confidence` (0-1) is a function of:

- source quality (mean reliability_score of cited evidence)
- number of independent sources
- agreement between sources (variance in stance)
- directness of evidence
- claim ambiguity (did claim extraction have to interpret vs. quote directly)
- recency of both the claim's subject and the sources
- claim complexity (single fact vs. compound causal claim)

Bands:

- `0.90–1.00` very high
- `0.75–0.89` high
- `0.60–0.74` moderate
- `< 0.60` **requires human review** — the dashboard flags these and
  Automatic Mode (if ever enabled) must never publish below this band.

Precise numeric confidence is an internal/dashboard value. Public-facing
copy uses qualitative language only, and only when the underlying
methodology can defend the specific number (§19 "do not display extremely
precise confidence numbers publicly unless there is a defensible
methodology") — the MVP does not publish confidence numbers on Instagram
at all, only the verdict category and sources.

## 7. Anti-hallucination validation (product spec §17)

Before a verdict can leave `researching` status, a deterministic
(non-LLM) validator runs:

1. Every `cited_evidence_id` on the verdict must reference a real
   `evidence` row for that claim.
2. Every `evidence` row's `source_id` must reference a `sources` row with
   a non-null `retrieved_at` and `full_text_storage_key` (i.e., it was
   actually fetched, not merely returned as a search snippet).
3. Any statistic/number/quote appearing in the verdict's
   `reasoning_summary` or in generated slide/caption text must appear
   (fuzzy-matched) inside the `relevant_passage` of a cited source.
4. Any URL surfaced to the user must equal a `sources.url` that was
   actually retrieved — never a model-generated URL.

If any check fails, the verdict is programmatically downgraded to
`UNVERIFIED` with `validation_status` recording which check failed, and
the fact_check is routed to human review rather than silently published.
This validator is code, not a prompt — it cannot be "argued out of"
failing a check.

## 8. Duplicate detection (product spec §27)

Before a fact_check can enter the review queue: match candidates by (a)
`reels.media_content_hash` exact/near match, (b) claim text embedding
cosine similarity above threshold against existing `claims`, and (c)
same primary source cited for a semantically similar claim. A match
short-circuits to `duplicate_of_fact_check_id` and status `rejected`,
surfaced to the reviewer as "DUPLICATE — DO NOT PUBLISH" rather than
silently discarded.

## 9. Corrections (product spec §26)

Corrections never overwrite history. A new `verdicts` row is created and
the old one is marked `is_current = false` with `superseded_by_id` set; a
`corrections` row records the reason and the evidence that changed. The
public fact-check page shows a visible correction notice with both the
original and updated conclusion, timestamped. A follow-up Instagram post
is a manual editorial decision (not automatic) for corrections judged
significant enough to warrant one.

## 10. Virality scoring (product spec §8, for Phase 5+ discovery)

```
virality_score =
    w1 * engagement_score        (likes+comments+shares, normalized)
  + w2 * velocity_score          (rate of change, not absolute count)
  + w3 * recency_score           (decays with age)
  + w4 * cross_platform_spread   (same claim seen on multiple platforms/accounts)
  + w5 * political_relevance     (LLM-scored: is this about governance/policy/elections/public officials)
  + w6 * claim_significance      (LLM-scored: public-understanding impact if false)
```

Weights are configuration, not hardcoded, and are logged with every score
(`audit_logs`) so the selection process is itself auditable. High view
count alone never qualifies content for fact-checking — `political_relevance`
and `claim_significance` are required to be above a floor regardless of
the other terms (product spec §8: "Avoid publishing fact-checks for
trivial content merely because it is viral").

## 11. Known limitations (state plainly, don't hide)

- Reel acquisition is human-in-the-loop; the system cannot claim to have
  "discovered" a reel it was handed a file for. `reels.discovery_source`
  records this honestly.
- Whisper transcription and OCR both have error rates, especially for
  non-English audio, accents, and stylized on-screen text; the transcript
  is displayed to the human reviewer and is editable before claims are
  (re-)extracted.
- Web search coverage is bounded by what the search provider indexes;
  `UNVERIFIED` is the correct and expected outcome for claims about very
  recent or very local events with limited English-language coverage,
  not a bug to be worked around by lowering evidence standards.
- Source reliability scoring encodes editorial judgment calls (e.g., tier
  classification of a given regional outlet); these weights are
  configuration reviewed by the human operator, not treated as ground
  truth.
