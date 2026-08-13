# IEEE_REVIEW.md — Phase 26

Status: 2026-08-14. A genuine, adversarial review simulation of
`research_paper/main.tex` as it stands after this session's full audit,
baseline correction, and all subsequent additions (Phases 0–25) — not a
review of the pre-audit draft. Each reviewer was instructed to find real
weaknesses, not confirm the paper is fine, consistent with how this
entire program has been run.

---

## Reviewer A: Machine Learning / NLP researcher

**Summary**: A methodologically unusual submission — its most important
contribution may be process, not results. The authors found a real
confound in their own baseline design mid-program, fixed it, and
reversed their own headline finding, disclosing all of it with equal
prominence. That is rare and commendable. The underlying evaluation,
however, remains severely underpowered, and the paper now contains so
many small, independent secondary analyses (main comparison $n=6$,
decomposition counterfactual $n=4$, error budget $n=4$/$n=5$,
entity-consistency $n=9$/$n=10$, synthetic validator $n=28$) that a
reader has to track which finding rests on which sample size throughout.

**Strengths**: the baseline-confound discovery and correction
(Section VII.A) is a genuine, verifiable piece of scientific integrity —
traced to a specific commit, fixed with a real re-run, not asserted. The
synthetic validator benchmark (Section IX) is a real methodological
contribution: it converts a previously-vague "this probably doesn't
generalize" disclosure into a tested, quantified negative result (0/4 on
novel phrasings). The formal "support validity" construct is a genuine
improvement over the undefined "trustworthiness" it replaces.

**Weaknesses**: (1) $n=6$ for the primary comparison remains the central
limitation no amount of secondary rigor resolves — every CI in Table
III/IV is wide enough to be consistent with a materially different true
result. (2) The "when does TruthLens help" table (12 cells, $n=6$) risks
reading as a post-hoc pattern fit dressed as a hypothesis; the paper's
own hedge ("stated as a hypothesis... not a conclusion this $n$ can
support") is appropriate but may not fully inoculate against this
critique. (3) The entity-consistency evaluation ($n=9$/$n=10$) and the
synthetic benchmark ($n=28$) are both real and honestly reported, but
neither is large enough to support the "recommendation: do not integrate
yet" conclusion beyond "obviously not yet" — a reviewer gains little
from the precision of a Wilson CI at this scale that a plain count
wouldn't already convey.

**Novelty**: 4/10. **Technical quality**: 8/10. **Experimental quality**:
6/10. **Clarity**: 6/10 (dense; 24 pages taxes this). **Reproducibility**:
9/10.

**Overall recommendation**: Weak Accept, conditioned on the concerns
below being addressed, not a clean accept.

**Major issues for rejection if unaddressed**: none that reflect
fabrication or hidden results — the paper's core problem is scale, not
integrity.

**Minor issues**: the "when-does-it-help" table should more prominently
restate its own $n=6$ caveat immediately adjacent to the table itself,
not only in the surrounding prose a reader might skip.

**Experiments still required**: a genuinely powered version of the
headline comparison (Section~\ref{sec:futurework}'s own estimate: on the
order of 40–60 paired items for reasonable power); a validator evaluation
on real (not synthetic) cases at a scale beyond $n=9$.

---

## Reviewer B: Multimedia / misinformation researcher

**Summary**: Strong domain instincts — the cross-post attribution problem
(Section X) is, on this evidence, a genuinely important structural
finding for this whole subfield, not just this paper, and it is unusual
to see a systems paper name and formalize a limitation this cleanly
rather than bury it in a future-work bullet. The dataset construction
methodology (Tier-1 ground truth, disjoint from development, disclosed
sourcing biases) meets the standard this subfield should hold itself to.
My concerns are about domain framing and comparison completeness.

**Strengths**: the cross-post attribution problem's Media/Post/Claim
formalization is exactly the kind of structural naming this literature
needs more of. The dataset card's explicit disclosure of ground-truth
-source bias (relying on BOOM Live/Alt News/Factly's own editorial
judgment, unaudited against a second source) is a real, easy-to-miss
threat to validity that most papers in this space do not name.

**Weaknesses**: (1) no system in this domain (TikTec, ShortCheck) is run
head-to-head against TruthLens — the related-work table (Section II.G)
is a literature comparison, not an empirical one, and the paper is
explicit about this, but a domain reviewer will still want to know how
TruthLens's claim-coverage numbers compare to an existing
checkworthiness-detection baseline on the same content, not just to
TruthLens's own internal baselines. (2) RQ5 (bias) is fully deferred;
the one qualitative observation offered (a government-actor verdict
treated no differently) is honestly caveated as weak evidence, but a
reviewer in this subfield will read the deferral as a real gap regardless
of how well it's disclosed. (3) The dataset's 9 items, sourced from three
Indian outlets, cannot support any claim about misinformation on
Instagram broadly, and the paper is careful not to make that claim — but
the paper's title and framing ("short-form political video") reads more
general than what 9 India-specific items can support; a narrower title
scoped to the actual domain would be more defensible.

**Novelty**: 5/10. **Technical quality**: 7/10. **Experimental quality**:
5/10. **Clarity**: 6/10. **Reproducibility**: 8/10.

**Overall recommendation**: Weak Accept for a workshop audience
(misinformation-detection or trust-and-safety focused); Weak Reject for
a general multimedia main track expecting broader empirical comparison.

**Major issues for rejection if unaddressed**: none rising to a
correctness problem; the domain-scope concern is about framing, not
validity.

**Minor issues**: consider a narrower title (e.g., "...of Indian
Political Instagram Video") matching the actual evaluated scope.

**Experiments still required**: at least one head-to-head comparison
against an existing checkworthiness-detection or misinformation
-classification baseline from this literature, not only TruthLens's own
internal baselines; the matched-pair RQ5 sourcing pass already scoped in
Future Work.

---

## Reviewer C: Very skeptical IEEE systems reviewer

**Summary**: I will be direct: this submission is currently unsuitable
for the venue it targets, on grounds unrelated to whether the underlying
research is sound. It is roughly 2.4$\times$ a typical IEEE conference
page limit (24 pages against a 10-page target the authors' own
`SUBMISSION_CHECKLIST.md` already names), and its prose style is
repetitive enough to read as padded even where every individual claim is
justified -- "rather than" appears 65 times in this document. A reviewer
with a stack of submissions and a fixed reading budget will not finish
this paper charitably at this length, regardless of its content's merit.

**Strengths**: the reproducibility infrastructure is genuinely
best-in-class for a paper at this stage -- exact regeneration commands
for every table and figure, tagged commits at every freeze point, a
disclosed distinction between "regeneratable from saved data" and
"re-runnable from scratch." The baseline-confound correction, if it
survives independent scrutiny, is a legitimately notable result about
research methodology in this specific subfield (LLM-pipeline
evaluation), arguably more citable than the architecture result itself.

**Weaknesses**: (1) Length and density, as above -- this is a rejection
-level issue on its own at most IEEE venues regardless of content. (2)
The paper stacks so many small-$n$ secondary analyses (the entity
-consistency prototype, the synthetic validator benchmark, the error
budget, the when-it-helps matrix) that a skeptical reader may reasonably
ask whether the volume of secondary evidence is compensating for the
primary result's weakness ($n=6$) rather than genuinely extending it --
even though each secondary analysis is individually honest and
well-scoped, the aggregate impression risks looking like more evidence
than the primary claim actually has. (3) The fact that the headline
result reverses within the same document (Section VII.A) is scientifically
commendable but will read, to an uncharitable reviewer skimming rather
than reading closely, as the authors not having their story straight --
this is a real risk of the disclosure-first approach, not a flaw in
taking it.

**Novelty**: 3/10. **Technical quality**: 7/10. **Experimental quality**:
4/10 (rigorous methodology does not substitute for statistical power).
**Clarity**: 5/10. **Reproducibility**: 9/10.

**Overall recommendation**: Reject in current form for a standard
10-page IEEE conference track. Would very likely support Accept for a
workshop track explicitly welcoming systems/methodology contributions
and negative results, or for a journal track with a generous page
budget, once trimmed for redundant phrasing.

**Major issues for rejection**: page length against stated venue limits;
prose density/repetition at a level that will cost the paper reviewer
goodwill independent of content.

**Minor issues**: the 65 occurrences of "rather than" should be varied;
several sections (the taxonomy in particular) could move to a
supplementary appendix per the authors' own Phase 23-equivalent
self-assessment.

**Experiments still required**: none — this reviewer's objections are
about presentation and scale, not missing experiments.

---

## Area Chair decision

Three reviews: Weak Accept (conditioned), Weak Accept (workshop) / Weak
Reject (main track), Reject (current form) / Accept (if trimmed and
retargeted).

**Decision: WEAK REJECT for the current draft as submitted to a standard
10-page IEEE conference track, with a specific, actionable revision
path, not a rejection of the underlying work.**

Reasoning: all three reviewers independently converge on the same two
structural issues -- insufficient statistical power for the scale of
claims being made (mitigated, not solved, by the paper's own honesty
about it), and a page/density problem unrelated to content quality. None
of the three reviewers found a correctness, integrity, or fabrication
problem; two explicitly credit the paper's self-correction as a genuine
strength. This is not a paper with a validity problem -- it is a paper
whose evidentiary scale and presentation have not yet caught up to its
own rigor.

**Concrete path to acceptance**, in the area chair's own priority order:
1. Trim to the target venue's actual page limit (Section~XV /
   `SUBMISSION_CHECKLIST.md` already names this as the top unresolved
   item; this review confirms it independently).
2. Either scale the dataset toward the $n=40$–$60$ power estimate already
   in this paper's own Future Work, or explicitly reframe the
   contribution around the methodology (self-auditing baseline design,
   the synthetic validator benchmark) rather than the architecture
   -vs-baseline comparison, which is what the evidence at this $n$ can
   actually support well.
3. A pass to reduce repetitive sentence construction, without removing
   the disclosure content itself -- a stylistic edit, not a content cut.
4. Consider a workshop or journal track with a more generous page budget
   and an audience that explicitly values negative/methodological
   results, as an alternative to trimming a 24-page paper down to 10.

---

## Addendum, 2026-08-14: partial progress on item 1

A trim pass moved the full failure-mode taxonomy, the superseded
baseline table, and several evidence-quality deep-dive subsections into
a new Appendix (excluded from IEEE TPS's page count by its own rules)
and tightened prose throughout. Total PDF: 24pp $\to$ 20pp; the Appendix
now begins on page 17, so the counted main body is roughly 17pp, down
from 24pp but still not 10pp. Every table, figure, and finding these
three reviewers evaluated is still present, unchanged in substance,
verified against `CLAIM_EVIDENCE_MATRIX.md`. This review's other three
items (statistical power, sentence-construction density, venue
retargeting) were not addressed by this pass and remain open exactly as
stated above -- this addendum reports progress on item 1 only, not a
re-review of the trimmed draft.
