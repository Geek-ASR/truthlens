# Multimodal Claim Coverage Evaluation (Day 4, RQ3)

Status: **real, live-run results against real ingested media — but small
(n=6), single-run (no repeat calls to average out LLM non-determinism),
and scored against unadjudicated draft ground truth
(`research/annotations/atomic_claims_draft.json`).** Every number below
should be read as directional, not conclusive, for exactly those
reasons — stated up front, not buried.

## What was actually run

`backend/research/multimodal/run_claim_coverage.py`: real ingestion
(fetch → transcribe → OCR → vision-context) of all 7 dataset items via
the system's own pipeline modules, followed by claim extraction called
directly (not through `extract_claims()`, to avoid writing extra `Claim`
rows for a pure research comparison — see "Methodological caveat" below)
under three input-modality conditions: `text_only` (transcript +
caption), `text_ocr` (+ on-screen text), `text_ocr_vision` (+ vision
-context description). All three conditions use `OllamaProvider`
directly — no Gemini fallback — for the same reason `BASELINE_SPEC.md`'s
baselines do: isolating the modality variable, not the escalation
cascade.

**Honest note on "4 modes":** the original brief that motivated this
experiment named four conditions including a separate "full multimodal"
mode. TruthLens's actual architecture has exactly three distinct input
signals feeding claim extraction — there is no real fourth condition
beyond "all three together," so `text_ocr_vision` **is** "full
multimodal" for this system. Presenting them as two different results
would have been fabricating a distinction that doesn't exist.

## Ingestion results: 6 of 7 items usable, 1 real, persistent failure

| Item | Ingestion | Media type |
|---|---|---|
| item-0001 | ✅ | video |
| item-0002 | ✅ | video |
| item-0003 | ❌ persistent "Instagram sent an empty media response," confirmed on 2 independent attempts with full retry/backoff each time | — |
| item-0004 | ✅ | video |
| item-0005 | ✅ (after a real bug fix — see below) | photo |
| item-0006 | ✅ | video |
| item-0007 | ✅ | video |

**A real bug was found and fixed in the middle of this run.** item-0005
initially failed with yt-dlp reporting `"No video formats found!"` —
correct information (it's a photo post), but the code's existing
photo-post fallback (`url_downloader.py`) only matched the literal
substring `"no video in this post"`, a different phrasing yt-dlp had
used for some other photo post previously. This specific phrasing was
never checked, so a genuinely fetchable photo post failed ingestion
outright instead of falling back to Open Graph tags. Fixed by matching
against a tuple of known phrasings (`_NO_VIDEO_MESSAGES`), mirroring the
existing `_RETRYABLE_MESSAGES` pattern already used one function over.
Two new regression tests added (`test_url_downloader_photo_fallback.py`,
now 16 tests); re-verified live immediately after the fix —
item-0005 now ingests successfully via the photo path. item-0003's
failure is a different, genuinely transient/persistent Instagram-side
condition (already in `_RETRYABLE_MESSAGES`, already retried 3× with
backoff both times it was attempted) — not a code bug, and not
"fixed," reported as a real, standing infrastructure limitation.

## Claim Coverage results (n=6, item-0003 excluded — no content to score)

| Condition | Covered | Coverage |
|---|---|---|
| text_only | 1/6 | 16.7% (Wilson 95% CI: 3.0%–56.4%) |
| text_ocr | 0/6 | 0.0% (Wilson 95% CI: 0.0%–39.0%) |
| text_ocr_vision (= "full multimodal") | 2/6 | 33.3% (Wilson 95% CI: 9.7%–70.0%) |

**Read these numbers as exactly what they are: 6 single, non-repeated
LLM calls per condition, with confidence intervals wide enough to
overlap almost entirely.** `text_ocr` scoring *below* `text_only` is a
real, reportable result, not one we are suppressing because it looks
bad for the "more modality is better" hypothesis (see Rule: "If
multimodal processing decreases performance on some subset: REPORT IT").
The most likely explanation, itself unverified, is single-call noise
compounded by a specific hallucination (below) — not a robust modality
effect — and this dataset is far too small to distinguish the two.

## The item-0004 case: the one clean, real, positive RQ3 result

This is the one item where the modality story is unambiguous. The
video's real Whisper transcript is badly garbled nonsense
(`"ऴलेगलतिम स्यभी है दिलगल् internationals"`), consistent with known
Whisper reliability issues on chaotic protest audio. But real OCR,
sampled across multiple frames, clearly and repeatedly captured on
-screen text asserting **"Delhi police dande me kil lagakar baccho ke
upar hamla kar rahi h"** ("Delhi police attacking children with a
nail-fitted baton") — the actual checkworthy claim, matching BOOM's own
verdict (TRUE) almost verbatim. `text_only` extracted nothing
resembling this claim (a nonsense fragment). `text_ocr` — despite
receiving the same real OCR text — happened to return one claim with
**empty text** on this particular run (a known, separately-documented
failure class, see below). `text_ocr_vision` correctly surfaced the
claim, though messily: 7 near-duplicate claims, one per noisy OCR-frame
variant, instead of one deduplicated atomic claim (a new failure mode,
below). Net result: only the multimodal condition produced *any* usable
signal for this claim, and the mechanism was OCR content the audio
transcript had no access to at all — a genuine, small-n demonstration
of exactly what RQ3 asks about.

## New failure modes found this pass (not yet in the paper's taxonomy)

1. **Near-duplicate claims from noisy OCR-frame variants, not
   deduplicated.** item-0004's `text_ocr_vision` condition returned 7
   claims that are all the same underlying assertion, each a
   slightly-differently-garbled OCR read of the same on-screen text
   across different sampled frames. The claim extractor treated each
   frame's noisy variant as a separate atomic claim rather than
   recognizing they're the same claim. Not caught by any existing
   deterministic check (`_extraction_looks_grounded` and
   `_extraction_looks_substantive` both look at claim-level
   substantiveness, not cross-claim redundancy).
2. **`importance` field values outside its declared [0,1] range,
   causing outright schema-validation failure.** item-0005's `text_only`
   run failed with `importance` = **-1**; its `text_ocr_vision` run
   failed with a run of claims numbered `importance` = 2, 3, 4, 5, 6 —
   which looks like the model substituting a claim *ordinal position*
   for the importance score once the claim list gets longer, not a
   score at all. Both failures happened purely on the local model
   (`OllamaProvider` directly, no Gemini fallback in this research
   script by design) and would, in the real production system, likely
   be silently rescued by `FallbackLLMProvider`'s Gemini retry — meaning
   this is a real failure mode normally *masked* by the escalation
   cascade, only visible because this experiment deliberately removed
   it to isolate the modality variable. Two of six items' `text_only`/
   `text_ocr_vision` conditions produced **zero usable claims** because
   of this, not because of the modality condition itself — a real
   confound in this pass's numbers, disclosed rather than smoothed over.
3. **The garbled/meta-commentary vision-output bug recurred 4 more
   times** (item-0002, item-0004, item-0006's `scene_description`, each
   producing text resembling a re-echoed prompt fragment rather than an
   image description; item-0007 and item-0001 produced empty vision
   output instead). Combined with the ~2 prior documented instances in
   the paper's existing taxonomy, this is now a **repeated, frequent**
   failure of the vision stage specifically, not the rare, single-case
   anecdote the current paper draft describes it as — this needs to be
   corrected in the next paper revision rather than left understated.
   Across all 6 successfully-ingested items, only item-0005's vision
   output was genuinely coherent and accurate ("Two men are standing in
   front of each other with one man wearing glasses and both having
   beards" — a real, correct description).

## A structural pattern in this dataset, found while drafting ground truth

Drafting atomic claims against the real ingested content (not just the
fact-checkers' summaries) surfaced something worth stating explicitly:
in **4 of 6** scoreable items (item-0001, item-0002, item-0005,
item-0006), the actual false/misleading claim does not exist anywhere
in *this specific post's own* transcript, caption, or OCR at all — it
was added by a *different* account when recirculating/recaptioning the
same underlying video. Only item-0004 (claim genuinely on-screen in the
ingested post) and arguably item-0007 (claim partially in the
ingested post's own transcript, degraded by cropping) have the
checkworthy claim actually present in the specific URL this dataset
points to.

This is a direct, structural consequence of how Tier-1 items are
sourced (`DATASET_SPEC.md`): a professional fact-checker traces a viral
false claim back to its *original, differently-captioned* source video,
and that original source video's own URL is what ends up in
`items.jsonl` (per the "genuine original video, not the exact reposting
account" convention already used since Day 2). This means a real
majority of this dataset's items may be **structurally unwinnable** for
single-post claim extraction, no matter how good modality coverage gets
— the missing piece is knowing how a video is being recaptioned
*elsewhere*, a capability (reverse-video-search / cross-post claim
matching) TruthLens does not have and was never claimed to have. This
is a significant, previously-unstated limitation of using this
particular Tier-1 sourcing method to evaluate claim extraction
specifically (as opposed to evaluating end-to-end verdict correctness,
where it works fine, since the verdict question is "is the claim as
stated true," not "did the system independently discover the claim").
Recommend the paper state this explicitly rather than let a low claim
-coverage number read as simply "claim extraction needs to improve."

## Methodological caveats, stated explicitly

- This script calls the claim-extraction LLM directly, **bypassing**
  `claim_extraction.py`'s own `_extraction_looks_substantive` /
  `_extraction_looks_grounded` checks and Gemini-escalation cascade —
  deliberately, to isolate the modality variable the same way
  `BASELINE_SPEC.md` isolates architecture. This means blank-text-claim
  artifacts appear in this experiment's raw output that the real
  production system would already filter or retry. **Do not read a
  blank claim here as "TruthLens would publish this" — it would not; it
  is what the raw model produces before TruthLens's own safeguards run.**
- n=6 items, single (non-repeated) LLM call per item per condition. No
  claim in this document should be read as a stable, reproducible
  modality effect — only as a real, honestly-reported directional
  signal plus two genuinely informative individual cases (item-0004's
  positive result, item-0005's schema-validation failures).
- Draft ground truth (`atomic_claims_draft.json`) is
  `llm_assisted_draft: true`, not yet reviewed by a human. The coverage
  numbers above will need recomputation once that review happens, and
  could change.

## What's next

1. Human review/adjudication of `atomic_claims_draft.json` (blocks
   trusting any coverage number here as final).
2. item-0003 retry at a later time, in case the Instagram-side
   condition is genuinely transient rather than permanent for this post.
3. Consider whether the "claim lives outside this post" structural
   pattern means Day 2's sourcing protocol needs a note added: prefer,
   where findable, Tier-1 items where the fact-checker's cited source
   URL *is* the misleading post itself (like item-0004), not only the
   traced-back original — since only those items are fair tests of
   claim-extraction coverage specifically.
4. The near-duplicate-OCR-claims and importance-out-of-range bugs are
   real findings worth a taxonomy entry each; neither has been fixed in
   this pass (Day 4's job was measurement, not remediation — consistent
   with Rule 12, these are flagged for a deliberate fix decision rather
   than patched reactively mid-experiment).
