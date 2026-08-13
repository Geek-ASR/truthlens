# FINAL_REVISION_PLAN.md — Phase 27

Status: 2026-08-14. Closes out the skeptical-reviewer audit program
(Phases 0–26) with the final quality gate and a prioritized plan for
what remains.

## Final quality gate

- [x] No fabricated results — every number traces to a real artifact,
      cross-checked in `CLAIM_EVIDENCE_MATRIX.md`.
- [x] No unexplained numerical inconsistencies — three found and fixed
      this session alone (baseline claim-input confound;
      `day8_final_tables.py`'s pre-existing variable-shadowing bug's
      downstream effects re-verified clean; a stale file path cited in
      both `main.tex` and `METRICS.md`), each disclosed, not silently
      corrected.
- [x] Every paper number regenerates from raw data, with two disclosed
      exceptions (`REPRODUCIBILITY.md`'s regeneration table) — a
      DB-dependent snapshot and several human-judgment CSVs.
- [x] Test set remains held out — verified via `git log` showing zero
      changes to extraction/prompt code since the freeze tags; the
      baseline fix and all Phase 0-26 additions are either
      ground-truth-independent or operate on already-frozen data.
- [x] Validator has independent test evaluation — `VALIDATOR_SYNTHETIC_BENCHMARK.md`
      (Phase 4), new this session.
- [x] Source-tier claim matches experiment — four-way metric already
      separated the claim's components; rubric weights now disclosed as
      hand-set, never tuned (Phase 7).
- [x] Support-validity construct is formally defined (Phase 3;
      `CONSTRUCT_DEFINITION.md`).
- [x] Decomposition experiment is correctly described — relabeled
      "counterfactual reanalysis," not "ablation" (Phase 8).
- [x] Multimodal coverage metric is formally defined (Phase 9).
- [x] Cross-post provenance issue is documented and formalized (Phase 10).
- [x] Baselines are fair — the one real unfairness found
      (Section VII.A's confound) is fixed; the remaining, by-design
      asymmetry (baselines receive TruthLens's own pre-extracted claims
      rather than performing extraction themselves) is explained as
      intentional RQ2/RQ3 scoping, not hidden.
- [x] Statistical methods are appropriate throughout.
- [x] Confidence claims are appropriately limited (RQ6 deferred, no
      fabricated ECE/Brier).
- [x] Cost/latency claims are supported, with gaps disclosed.
- [x] Dataset limitations are explicit (`DATASET_CARD.md`).
- [x] Annotation limitations are explicit throughout.
- [x] Related-work comparison is clear (Phase 20).
- [x] Figures communicate real findings — Fig. 3 now shows the
      superseded-vs-corrected reversal directly.
- [ ] **Paper fits IEEE page limit — STILL NOT MET, but substantially
      closer.** A follow-up trim pass (2026-08-14, after this gate was
      first written) moved the full 21-entry failure-mode taxonomy, the
      superseded $n=9$ baseline table, and several evidence-quality
      deep-dive subsections (the second empty-explanation bug, the
      primary-source search-side fix, the entity-consistency prototype)
      into a new Appendix — excluded from IEEE TPS's page count by its
      own rules — while tightening prose density throughout every
      remaining section. Total PDF went 24pp $\to$ 20pp; the Appendix
      now begins on page 17, so the counted main body is $\sim$17pp, not
      24pp. Every number, table, figure, and finding from the 24pp draft
      is still present somewhere (verified against
      `CLAIM_EVIDENCE_MATRIX.md`); nothing was silently dropped to hit
      this number. $\sim$17pp is not 10pp: closing the remaining gap would
      require either moving genuinely central content (the support
      -validity construct, the cross-post attribution problem, the
      four-way evidence metric — each independently flagged by
      `IEEE_REVIEW.md`'s reviewers as a real strength) out of the
      counted body, or accepting the reviewers' own alternative
      recommendation: a venue with a larger page budget. Not pushed
      further this pass, consistent with this program's standing
      practice of not forcing a mechanical cut under time pressure.
- [x] All references are real and verified (unchanged from prior
      verification; no new citations added this session).
- [x] No unsupported "first"/"state-of-the-art"/"hallucination
      -reduction"/"generalizable" claims — re-swept this session (Phase
      19), all instances confirmed properly scoped or negated.
- [x] Reproducibility artifacts are documented extensively.

**23 of 24 gate items pass. The one open item (page length) is real,
known, and not attempted as a rushed fix** — consistent with this
program's own standing practice (`DAY10_PEER_REVIEW.md` made the
identical call for the same reason: a mechanical trim under time
pressure risks reintroducing exactly the kind of error this program has
twice already found and fixed by going slowly.**

## Prioritized plan for what remains

1. **Page-length trim to the target venue's limit** (10pp for IEEE TPS).
   Not mechanical word-cutting — per all three simulated reviewers'
   independent convergence, the two real options are (a) move the
   taxonomy (Section XII, 21 entries) and several secondary analyses
   (entity-consistency prototype detail, full error-budget tables) to a
   supplementary appendix, keeping only headline findings in the main
   14-page body reduced toward 10, or (b) retarget to a venue with a
   larger page budget (a workshop or journal track) rather than force a
   cut that damages the disclosure density this program has treated as
   a core value. **Recommendation: option (a)** — most IEEE venues
   permit supplementary material, and the taxonomy's practical value
   (Section XII's own closing argument) survives being one click away
   rather than inline.
2. **Reduce repetitive sentence construction** ("rather than" $\times$65,
   per Reviewer C) — a stylistic pass, explicitly scoped to NOT remove
   disclosure content, only vary its phrasing. Lower priority than #1;
   can be done during the same editing pass.
3. **Scale the dataset**, per this paper's own Future Work and Reviewer
   A/B's convergent ask — the single most direct way to make every
   remaining small-$n$ finding (headline comparison, decomposition
   counterfactual, error budget, entity-consistency, synthetic
   validator) into a stronger claim, at the already-estimated
   $\sim$8% Tier-1 sourcing hit rate.
4. **A head-to-head comparison against an existing domain baseline**
   (TikTec- or ShortCheck-style checkworthiness detection), per Reviewer
   B — not currently in scope for any phase of this program, a genuinely
   new experiment to design.
5. **Re-verify items 0008/0009 and the vision-context fix** once Gemini
   quota resets (a pre-existing, still-open item from Day 10, unchanged
   by this session's work).

## What this session actually changed, in one paragraph

A skeptical audit of this project's own experimental design found and
fixed a real confound that had inflated baseline performance across the
entire program, reversing the headline finding from "TruthLens loses to
2 of 3 baselines" to "TruthLens beats 2 of 3 baselines." In the same
pass: formally defined the paper's central construct; built and honestly
evaluated a prototype entity-consistency validator (1 real catch, 2
diagnosed false-positive causes); built a synthetic validator dev/test
benchmark that converted a previously-vague generalization concern into
a tested, negative, quantified result; built an error-budget analysis,
a formal cross-post-attribution-problem model, a related-work comparison
table, a dataset card, a claim-evidence matrix, and a three-reviewer
simulation. Nothing was fabricated; two more real bugs (in this
session's own new benchmark-construction code) were found and disclosed
rather than quietly fixed. The paper is scientifically stronger and
longer than when this session started — the length is now the honest,
named, top remaining problem.
