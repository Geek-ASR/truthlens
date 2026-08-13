# Day 10: Three-Reviewer Self-Audit

Status: a genuine, adversarial self-review written from three distinct
reviewer perspectives against `research_paper/main.tex` as it stood after
Day 9's rewrite, before this document's own "warranted fixes" were
applied. Each reviewer was asked to find real weaknesses, not to confirm
the paper is fine — per the governing brief's own instruction that a
Day 10 audit should surface reviewer criticisms, not manufacture a clean
bill of health. Fixes actually applied are listed at the end, along with
concerns judged real but left open (with reasons).

---

## Reviewer 1: Statistical/methodological rigor

**Summary**: The paper is unusually honest about its own limitations —
more so than most submissions at this scale — but honesty about a
weakness is not the same as the weakness not existing. My concerns are
about statistical validity and framing, not about disclosure.

**Concerns:**

1. **$n=9$ ($n=6$ for the headline result) is very small**, and every
   confidence interval reflects that (e.g., Table IV's 33.3% carries a
   [9.7%, 70.0%] interval spanning most of the plausible range). The
   paper reports this correctly, but the abstract's framing of the
   headline finding as if it were a stable characterization of the
   architecture risks over-reading a single small draw. Recommend the
   abstract state the interval width alongside the point estimate, not
   just in the body.
2. **The "label accuracy and trustworthiness are different axes"
   reframing is the paper's central rhetorical move, and it is real, but
   it was also constructed *after* seeing the headline negative result.**
   A skeptical reader could reasonably ask whether this is a genuine,
   independently-motivated finding or a post-hoc reframing of a
   disappointing number. The paper's own disclosure of the validator
   check's calibration circularity (Section IX) partially preempts this,
   but the connection between "this reframing was motivated by the
   negative result" and "the specific fix's calibration was also
   motivated by reading the negative result's cases" could be drawn more
   explicitly as the same underlying methodological tension, not two
   separate disclosures.
3. **McNemar's test at 2 discordant pairs is close to uninformative**
   ($p=0.5$ could result from almost any true effect size at this $n$).
   The paper already says this ("reported for completeness, not as
   evidence of anything on its own"), which is the right call, but I'd
   have liked one sentence on what $n$ would be needed for this specific
   comparison to have reasonable power, so a reader has a concrete target
   rather than just "more data would help."
4. **Baselines 1–3 receive claims already extracted by TruthLens's own
   claim-extraction stage.** This means the headline comparison is not
   quite "TruthLens vs. simpler alternatives" — it's "TruthLens's
   downstream stages, penalized when its own upstream stage fails, vs.
   simpler alternatives that never had to run that upstream stage at
   all." The paper's Threats to Validity section already names this, but
   it is arguably the single most important methodological caveat on the
   headline number and could be surfaced earlier, e.g., in the Results
   section itself rather than only in Threats to Validity several
   sections later.

**Recommendation**: Minor-to-moderate revision. The statistics are
correctly computed and honestly reported; the concerns are about framing
and where in the paper certain caveats appear, not about hidden errors.

---

## Reviewer 2: Domain expertise (fact-checking / misinformation)

**Summary**: The dataset construction methodology (Tier-1 ground truth
from independent professional fact-checkers, disjoint from development
data) is the right standard for this subfield, and the paper is
unusually candid about not reaching the scale that standard ideally
wants. My concerns are about domain framing.

**Concerns:**

1. **Ground-truth-source bias is not discussed.** The paper relies on
   BOOM Live, Alt News, and Factly's own published verdicts as ground
   truth — a defensible and standard choice, but these organizations'
   own editorial track records and any systematic leanings they might
   have are not acknowledged anywhere as a limitation distinct from
   RQ5's question (which is about *TruthLens's* bias, not the ground
   -truth source's). A paper this careful about disclosing threats to
   validity should name this one too, even briefly.
2. **The structural finding that most false claims live outside the
   specific post being checked (Section X) is, on this evidence, larger
   than a future-work item — it may be close to a ceiling on what
   single-post claim extraction can ever achieve in this domain.** The
   paper does give this real prominence (calling it "the most important
   finding" in places), which I credit, but Future Work still lists
   video-provenance verification as one bullet among ten. Given the
   paper's own data, this arguably deserves to be framed as *the* primary
   limitation of the entire claim-extraction-based approach, not one item
   in a list.
3. **RQ5 is fully deferred rather than illustrated with even one informal
   case.** The paper does include one qualitative observation (the Delhi
   Police case), which helps, but a reader is left with literally zero
   sense of what a matched-pair comparison might look like, even as a
   worked example acknowledged to be anecdotal.

**Recommendation**: Accept with minor revisions. The methodology is
sound for the domain; I'd like to see ground-truth-source bias named
explicitly and the provenance-verification gap given a more prominent
framing than "future work item #3."

---

## Reviewer 3: Reproducibility and systems rigor

**Summary**: Strong for a paper at this stage — exact commands, a real
environment lock, tagged freeze points, and (unusually) a fully disclosed
account of a bug found in the paper's own table-generation tooling while
preparing this exact submission. My concerns are about what "reproducible"
actually means here, and about a few remaining gaps.

**Concerns:**

1. **"Regeneratable from saved data" and "re-runnable from scratch" are
   different claims, and REPRODUCIBILITY.md does not clearly separate
   them.** Every LLM call in this pipeline is unseeded (disclosed), so
   even Table III/IV's numbers — fully regeneratable from the saved
   `.jsonl`/`.json` files by the documented script — would **not**
   reproduce identically if someone re-ran the actual baselines and full
   pipeline against live Ollama/Gemini today. This is stated in the
   "Random seeds" section but not connected explicitly to what it implies
   about the specific tables/figures a reader might assume are "fully
   reproducible" from the regeneration-command table above it.
2. **Two figures/tables (validator confusion matrices, evidence
   tier/stance distribution) are not machine-derivable from a committed
   artifact at all** — one depends on an unadjudicated human judgment
   column, the other on a live database query that could not be run in
   the environment used to prepare this revision. Both are disclosed,
   which is the right baseline behavior, but neither has even a saved
   query/script committed for a future environment that *does* have the
   stack running to use directly — a reader has to reconstruct the query
   from prose.
3. **The two general fixes made after the `truthlens-day8-frozen` tag
   (the new validator check, the vision-context substantiveness check)
   sit on `main` with no tag of their own**, making "which exact commit
   produced the addendum numbers in Section IX" answerable only via
   `git log`, not a single documented ref.
4. **Page count (21 pages) is roughly double even the most generous
   realistic venue limit found during Day 10's venue search** (IEEE TPS's
   research track: 10 pages). This is a submission-readiness blocker, not
   a cosmetic issue, and should be flagged with that severity rather than
   folded into general polish.

**Recommendation**: Accept pending the tag and the seed/reproducibility
-scope clarification; the page-count gap is a submission-checklist item,
not a correctness concern.

---

## Fixes applied in response to this review

1. **(R3-3)** Tagged the current commit `truthlens-day9-general-fixes` so
   the exact code state behind Section IX's addendum numbers has its own
   ref, not just a `git log` position.
2. **(R3-1)** Added an explicit "regeneratable $\neq$ re-runnable"
   clarification to `REPRODUCIBILITY.md`, naming Tables III/IV/V
   specifically as the case a reader could otherwise misread.
3. **(R2-1)** Added a one-sentence, named threat to validity in
   Section XIII (`sec:threats`) disclosing reliance on the ground-truth
   sources' own editorial judgment, distinct from RQ5's question about
   TruthLens's own bias.
4. **(R1-3)** Added one sentence to Future Work naming the sample size a
   well-powered version of the headline comparison would need, rather
   than leaving "more data would help" unquantified.

## Concerns judged real but left open, with reasons

- **(R1-2, reframing-after-seeing-the-result)**: judged a legitimate
  tension inherent to any honest post-hoc analysis of a negative result,
  not a defect specific to this paper's writing; already partially
  addressed by the existing circularity disclosure in Section IX. Left
  as a standing tension for a reader to weigh, stated here rather than
  argued away.
- **(R1-4 / R3 severity framing)**: the claim-extraction-coverage caveat
  on the headline comparison already exists in Section XIII; moving it
  earlier (into Section VII itself) is a real improvement but was judged
  a structural edit better done alongside the page-count trim this
  review also flags, not in isolation — both are named together as the
  single largest remaining pre-submission task (see the submission
  checklist).
- **(R2-2, provenance-verification prominence)**: judged already
  reasonably prominent (named "the most important finding" in three
  places across Sections X, XIII, and the Conclusion); reordering Future
  Work's list to put it first is cosmetic and was not done to avoid
  churning a section without a substantive reason.
- **(R2-3, RQ5 worked example)**: judged out of scope for this pass —
  constructing even an informal matched-pair illustration risks the
  exact thing Rule 3 of the governing protocol warns against (adjusting
  analysis after seeing how it looks), since any pair chosen now would
  necessarily be chosen with full knowledge of both items' verdicts.
- **(R3-2, no committed query for the DB-dependent figure)**: a fair
  ask; not done in this pass because writing and testing a query against
  a database that is not currently running risks committing an unverified
  script, which is a worse outcome than the current honest prose
  description. Named as a concrete Future Work item instead.
- **(R3-4 / page count)**: the largest single remaining gap. Not
  mechanically trimmed in this pass — cutting roughly half the paper's
  length without re-verifying every remaining claim's context risks
  reintroducing exactly the kind of error this same audit already found
  twice (Section GROUND_TRUTH.md's 6-vs-7 miscount, day8_final_tables.py's
  variable-shadowing bug). Recorded explicitly as the top item on the
  submission-readiness checklist rather than rushed.
