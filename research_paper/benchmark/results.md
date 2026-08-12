# Pilot benchmark results

Real, live `POST /api/reels/quick` runs against `claims.jsonl` entries.
These are the first two times TruthLens has ever been run against
content other than the one mandatory development test reel.

## bm-0001 — NEET 2026 "success story" video (BOOM Live)

- Fact-check ID: `67760c9f-bf8a-4d95-ba8e-87eb2751d0b1`
- Ground truth (BOOM, Tier 1): **FALSE**
- TruthLens overall verdict: **MOSTLY_FALSE** (maps to `FALSE` bucket on
  the collapsed 4-way scheme) — **agrees with ground truth**.
- TruthLens's own claim decomposition did NOT match BOOM's claim framing
  1:1. BOOM's official `ClaimReview` claim was about the video's timing/
  context ("captures NEET 2026 candidates celebrating after the July 16
  results"). TruthLens instead atomized the reel into three different
  claims from its own caption/transcript reading: (1) the 681/720 score
  claim — `UNVERIFIED`; (2) BHU being a real medical university in UP —
  `UNVERIFIED` (this is trivially, uncontroversially true, and it's a
  real weakness that the pipeline couldn't confirm it); (3) "the
  candidate is a paan shop owner's son" — `MOSTLY_FALSE`, which is the
  claim that dragged the overall verdict down and is where TruthLens's
  own reasoning happened to land closest to BOOM's actual finding (the
  video predates and isn't about NEET 2026 at all).
- This is an important, honest methodological finding for the benchmark
  protocol (Section "Scoring procedure," step 3): reel-level verdict
  comparison worked cleanly here, but claim-level comparison against an
  external fact-checker's claim framing is not a trivial 1:1 match and
  needs real semantic matching, exactly as flagged as a risk in
  `PROTOCOL.md` before this test was run.
- Evidence quality: 20 sources retrieved, 19 classified `irrelevant`, 1
  `supports` — including genuinely nonsensical hits from the free search
  backend (`my.gov.au`, a Russian pizza-restaurant site) for an
  India-specific query. Reinforces the paper's search-recall finding
  with an independent second data point, worse than the 55.6%
  irrelevant-rate average from development telemetry (95% here).
- Deterministic validation fired again on fresh, previously-unseen
  content: the primary claim's verdict was downgraded
  (`downgraded_missing_citation` — cited evidence not present in the
  claim's own evidence matrix), caught automatically, not shipped
  unflagged.
- Rendered conclusion slide visually verified — correct verdict badge,
  correct claim table, correct source citation, legible.

## bm-0002 — Mexico World Cup video falsely linked to Delhi protest (Alt News)

- Fact-check ID: `0a683678-c9fa-48a6-9623-e638a320a43d`
- Ground truth (Alt News, Tier 1): **FALSE** (video is Mexico World Cup
  celebration footage, not the Delhi protest it's captioned as).
- TruthLens overall verdict: **MOSTLY_FALSE** — matches ground truth at
  the surface label level, but **for the wrong reason**, and this needs
  to be reported as a right-answer/wrong-reasoning case, not a clean win.
  See "Two new bugs found" below — this is the more important result
  from this pilot than the label match.

### Why the label match is misleading here

The reel's caption is a Hindi moral commentary about protest conduct
("in a democracy every citizen has the right to peaceful protest, but
protest language should have dignity...") — it never states the actual
misleading claim in words. The misleading claim is entirely visual: a
Mexico World Cup celebration clip captioned as if it depicts the Delhi
protest. TruthLens's claim extraction, which works from transcript/OCR/
caption text, extracted two claims from the caption's *moralizing text*
("citizens have the right to protest peacefully"; the poster's
organizational title) — neither of which is the claim that was actually
false. **TruthLens never identified or checked the one thing that was
actually misleading: what the video shows.** The `MOSTLY_FALSE` label is
therefore not evidence the system caught the misinformation; it's a
coincidental match from unrelated claims.

**This is a significant, systemic limitation, not a one-off:** both
pilot cases (bm-0001 and bm-0002) are miscaptioned/out-of-context video
— reposting real footage with a false claim about what it shows — which
is the single most common pattern in the professional fact-checks
surveyed while building this benchmark (see PROTOCOL.md sourcing notes).
TruthLens's architecture has no video-provenance/reverse-image-search
capability, only text-derived claim extraction. It may be structurally
poor at catching the dominant real-world failure mode in this domain.
This belongs in the paper's Limitations section and as the top Future
Work item, arguably ahead of primary-source retrieval.

### Two new bugs found (independent of the above)

1. **Entity confusion between similarly-named organizations.** Evidence
   retrieval, researching "Kunwar Vishnu Singh Rajput is an
   organizational secretary of Karni Sena," pulled in a Wikipedia
   article about **Sri Ram Sena** — a real but *different* Indian
   organization (name collision on "Sena"). The evidence-analysis stage
   labeled this source's stance as `contradicts` rather than
   `irrelevant`, which is itself a misclassification: an article about a
   different organization doesn't "contradict" a claim about this one,
   it simply doesn't address it.
2. **Ungrounded, unsupported claim reached the published slide via the
   overall-verdict "why" paragraph.** The rendered conclusion slide's
   "WHY?" text states protest conduct claims "suggest that Karni Sena
   may be an unrelated organization with violent ideology" — language
   pulled from the *Sri Ram Sena* Wikipedia article's description of
   *that different organization's leader* calling for violence against
   a religious minority, now misattributed to Karni Sena in the
   published output. This is a real, serious hallucination: an
   unsupported, reputationally significant claim about a real
   organization, generated by the `_generate_why_paragraph` LLM call
   (`app/pipeline/reel_content.py`) and published without being caught.

   **Root cause: a real gap in validation coverage.** The deterministic
   validator (Section IV of the paper) checks citation existence, source
   -fetch existence, and number-grounding — but only for **per-claim
   verdicts**. `_generate_why_paragraph`'s only safety net is falling
   back to the deterministic rule-based reasoning string on an
   *exception* (a Python error) — it has no check that its actual
   generated text is grounded in, or even topically about, the right
   entity. This slipped through every existing safety mechanism.

   **This never reached a real audience** — it stayed in `ready_for_review`
   status in the local dev database and was never approved or published
   to Instagram. But it is exactly the class of failure the entire
   validation architecture exists to prevent, finding a real gap in that
   architecture's coverage. This should be treated as a priority fix,
   not just a paper footnote.

   **Fixed** (commit `2c12e36`, same day): once a verdict's
   `validation_status` isn't `passed`, none of its free-text reasoning is
   reused for display or as further LLM input — only the label and a
   generic, non-fabricated note are. Applied at both real exposure points
   (`EvidenceCard.answer_text`, and the why-paragraph's `claims_block`
   input) in `app/pipeline/reel_content.py`. Also fixed, found while
   tracing this: `validation.py`'s number-grounding check was extracting
   UUID fragments from inside `[[evidence_id=...]]` citation markup and
   flagging them as unsupported statistics — a separate, real
   false-positive bug that caused this specific verdict to be downgraded
   for the wrong stated reason. Verified directly against this exact
   database row (not just synthetic test data) — see commit message for
   the before/after. This should be treated as evidence the
   validation-gap pattern is real and worth watching for elsewhere, not
   as "solved forever": the underlying entity-confusion in evidence
   retrieval (Karni Sena / Sri Ram Sena) is unaddressed and could recur
   in a form the current checks don't catch.
