# Day 10 Final Report: 10-Day IEEE Evaluation Program

Status: 2026-08-13. This is the closing report for the program that began
at Day 1's audit (git tag `truthlens-pre-ieee`) and produced a full,
honest, held-out evaluation of TruthLens across Days 1–10. Every item
below traces to a versioned artifact under `research/` or
`research_paper/main.tex`; nothing here is summarized from memory.

1. **Title**: "TruthLens: A Verification-Gated Pipeline for
   Evidence-Grounded Fact-Checking of Short-Form Political Video"
   (unchanged since before this program — still accurate to what was
   built and evaluated).

2. **Central research question**: Can a verification-gated,
   evidence-grounded architecture reduce unsupported fact-checking
   outputs while preserving or improving factual correctness in
   short-form political media?

3. **RQ1–RQ6 and status** (`main.tex` Table I): RQ1 (validation reduces
   unsupported output) — yes, directional, $n=9$. RQ2 (decomposition
   beats single-shot search) — not on this sample end-to-end; yes for
   decomposition specifically, $n=4$. RQ3 (multimodal improves coverage)
   — directional yes, $n=6$. RQ4 (source-tiering improves evidence
   quality) — yes for tier classification; a distinct usable-evidence
   gap remains. RQ5 (comparable standards across actors) — deferred, no
   matched pairs exist. RQ6 (confidence correlates with correctness) —
   deferred, sample too small to calibrate.

4. **Contributions (5, all experimentally supported)**: (1) a held-out
   Tier-1 benchmark + controlled baseline/ablation comparison; (2) an
   empirical demonstration that verdict-label accuracy and output
   trustworthiness are separable, independently-moving properties
   (validator recall 16.7%→40% with zero accuracy change); (3) a
   controlled claim-decomposition ablation showing a real accuracy gain
   (50.0% vs. 25.0%, $n=4$) where the architecture's advantage actually
   materializes; (4) a four-way evidence-quality analysis (68.75% vs.
   18.75% gap between relevance and usable extraction); (5) a
   cross-referenced taxonomy of 21 real failure modes, 8 found this
   session.

5. **Dataset size**: 9 items, all Tier 1 (professional-fact-checker
   -verified), disjoint from development data. 6 have a resolved verdict
   from every system configuration (item-0003 permanently unfetchable;
   items 0008/0009's full-TruthLens condition blocked by real Gemini
   quota exhaustion). `research/dataset/items.jsonl`.

6. **Annotators**: One primary annotator (this project) for any Tier-2
   -style draft judgment (claim-coverage matching, evidence-relevance
   calls, validator TP/FP/TN/FN calls). Zero annotators for Tier-1
   headline verdicts — those are the professional organizations' own
   published verdicts, which is the entire methodological point.

7. **Inter-annotator agreement**: Not computed, and explicitly not
   fabricated to fill the gap. No IAA condition currently exists in this
   dataset (single annotator, no Tier-2 items) — stated plainly in
   `GROUND_TRUTH.md` and Section VI of the paper.

8. **Baselines (4, all real, all run)**: (1) LLM-only, $n=9$: 22.2%. (2)
   Search+LLM, $n=9$: 77.8%. (3) Search+RAG+LLM, $n=9$: 55.6%. (4)
   TruthLens-minus-validation (`SKIP_VALIDATION` flag, a config flag not
   a code fork) — its result is the RQ1 unsupported-output-rate
   comparison, not a separate accuracy row.

9. **Ablations (3)**: validation ablation (RQ1, above); claim
   -decomposition ablation ($n=4$: 25.0% single-claim vs. 50.0%
   multi-claim); source-tier ablation (domain-restricted retrieval:
   $\sim$11%→95% tier-classification rate, on a distinct, smaller query
   sample).

10. **Main results (headline finding)**: On the paired 6-item set (the
    only fair comparison), full TruthLens (33.3%, 2/6) does **not** beat
    Baseline 2 (66.7%, 4/6) or Baseline 3 (50.0%, 3/6). Reported first,
    traced to 2 claim-extraction-coverage failures + 2 validator false
    negatives, not a mysterious general weakness. McNemar $p=0.5$
    (uninformative at this $n$, reported for completeness).

11. **Validator results**: Original: Precision 100% (1/1), Recall 16.7%
    (1/6), $n=9$. After two general fixes: Precision 100% (2/2), Recall
    40% (2/5) — with a disclosed circularity (the new check's phrase list
    was written after reading the 2 cases it now catches) and a disclosed
    regression (one case moved from an accidental true positive to a
    false negative when an unrelated bug fix removed its false trigger).

12. **Evidence quality results**: $n=68$ sources, 9 claims. Four-way
    metric: tier classification 23.5%; topical relevance among
    primary-tier sources 68.75%; fetch-success 16/16 (by construction);
    usable-evidence extraction 18.75%. The 68.75%/18.75% gap is the
    single most important finding of that analysis — retrieval finds
    real, on-topic sources; most are too generic to confirm one specific
    fact.

13. **Multimodal results**: $n=6$ (item-0003 excluded). text_only 16.7%,
    text_ocr 0.0%, text_ocr_vision (full) 33.3%. One clean positive case
    (item-0004: OCR recovered a claim audio transcription missed
    entirely). Structural finding: in 4 of 6 items, the actual false
    claim lives outside the specific post's own content — a likely
    ceiling on single-post claim extraction in this domain, independent
    of modality coverage.

14. **Bias results (RQ5)**: Not evaluated quantitatively — no matched
    pairs exist in the 9-item dataset (BJP has the most items, 3, none
    topic-matched against another actor). One qualitative observation
    reported (system reached FALSE against a government actor's claim),
    explicitly not treated as evidence of neutrality.

15. **Calibration results (RQ6)**: Not computed — 9 confidence values
    cannot meet the pre-registered "no bin under 3 items" gate. One
    qualitative, heavily caveated observation: the two highest-confidence
    verdicts in this sample were both judged unreliable or wrong.

16. **Efficiency results**: Baseline 2: 1 LLM call, ~15.9s, $0. Baseline
    3: 1 LLM call, ~17.8s, $0. Full TruthLens: ~9.6 LLM calls/claim
    (derived from 7.56 sources/claim), latency not captured (disclosed
    gap). Baseline 4 identical call profile to full TruthLens by
    construction.

17. **Negative/unfavorable results, reported with full prominence**: the
    headline finding (#10); the multimodal `text_ocr` condition scoring
    *below* `text_only` (0.0% vs. 16.7%); the validator-fix regression
    (#11); RQ5/RQ6 deferrals (#14–15); a real bug found in this program's
    own table-generation script that silently wrote wrong numbers to a
    persisted JSON summary (caught during Day 10 figure verification, now
    a 21st taxonomy entry).

18. **Limitations (headline list, full list in Section XIII)**: $n=9$,
    single annotator, no IAA; single domain/country/language-mix; the
    new validator check's calibration circularity; the vision-context
    fix not independently re-verified against accuracy (quota-blocked);
    item-0003 permanently excluded; baseline comparison entangles
    architecture with claim-extraction coverage; `.gov.in` fetch
    -reliability gap still open; ground-truth-source bias not audited
    (added this pass).

19. **System changes made this program** (all with a deterministic check
    + regression test + live re-verification): baseline-isolation
    -confound fix (Day 3); photo-fallback phrasing gap fix (Day 4);
    UUID-leak-in-citation-markup fix (Day 5); evidence-analysis empty
    -explanation substantiveness check (Day 6); new validator Check 4,
    label/reasoning consistency (Day 8, post-freeze); vision-context
    prompt-echo substantiveness check (Day 8, post-freeze);
    `MissingGreenlet` fix in the validator-audit research script (Day 8);
    `day8_final_tables.py` variable-shadowing fix (Day 10).

20. **Paper changes this program**: complete Day 9 rewrite (abstract
    through conclusion, ~1,300 → ~2,100 lines) around real results
    instead of development telemetry; 8 new named figures + a TikZ
    architecture diagram (Day 10); taxonomy grown from 13 to 21 entries;
    a real 6-vs-7 dataset-composition miscount found and fixed (Day 10
    audit); 4 fixes applied from a 3-reviewer self-audit (Day 10).

21. **Target venues** (real, verified live, not fabricated): best
    topical fit is **IEEE TPS** ("Trust in social media – AI-enabled
    disinformation and misinformation at scale" is an explicit named
    topic), 10-page limit — but its 2026 rounds have passed or are 2 days
    out; realistic target is **its 2027 cycle**. Also considered:
    **IEEE BigData 2026** (real Aug 21, 2026 deadline, weaker topical
    fit, unrealistically tight given remaining polish); **MisD@ICWSM**,
    **FEVER@EACL**, **CLEF CheckThat!** (all excellent topical fits, all
    2026-cycle deadlines already passed — realistic target is each
    venue's next cycle). No forced recommendation of a rushed submission
    to a weak-fit open deadline.

22. **Page count**: 21 pages (compiled, `tectonic main.tex`), against a
    10-page realistic venue limit. **Not yet trimmed** — flagged as the
    single largest remaining pre-submission task, deliberately not done
    mechanically this pass (see `DAY10_PEER_REVIEW.md`, R3-4).

23. **Reproducibility status**: environment lock committed (130
    packages); 3 git tags mark every freeze point including the new
    post-Day-8-fixes boundary; every table/figure has a documented,
    verified regeneration command; 161/161 tests pass; 2 disclosed gaps
    (a live-DB-dependent figure, unseeded LLM calls meaning results are
    "regeneratable from saved data," not "re-runnable to the same
    numbers from scratch" — this distinction is now explicit in
    `REPRODUCIBILITY.md`).

24. **Reviewer criticisms**: 3 independent self-review passes
    (statistical/methodological, domain expertise, reproducibility/
    systems), 13 concerns raised, 4 fixed (audit-boundary tag,
    regeneratable-vs-re-runnable clarification, ground-truth-source-bias
    disclosure, a concrete power-analysis target for future sourcing), 9
    recorded open with explicit reasons. Full text: `DAY10_PEER_REVIEW.md`.

25. **Remaining risks**: page-count-vs-venue-limit gap (#22); the new
    validator check's untested generalization to differently-phrased
    reasoning; items 0008/0009 and the vision-context fix's real-world
    accuracy impact both blocked on Gemini quota reset; dataset still
    3–20x smaller than even this program's own reduced target;
    `.gov.in` fetch-reliability gap unresolved; no unified
    `docker-compose` stack.

26. **File paths (primary artifacts)**: paper — `research_paper/main.tex`
    / `main.pdf`; figures — `research_paper/figures/fig*.pdf`; dataset —
    `research/dataset/items.jsonl`; results — `research/results/*.json*`;
    evaluation write-ups — `research/{DAY8_RESULTS,VALIDATOR_EVALUATION,
    EVIDENCE_EVALUATION,MULTIMODAL_EVALUATION,
    BIAS_CALIBRATION_EFFICIENCY}.md`; this program's own process docs —
    `research/{EXPERIMENT_PLAN,BASELINE_SPEC,DATASET_SPEC,METRICS,
    GROUND_TRUTH,REPRODUCIBILITY,DAY10_PEER_REVIEW,
    SUBMISSION_CHECKLIST}.md`; table/figure generators —
    `backend/research/{day8_final_tables,day10_figures}.py`.

27. **Regeneration commands**: `./backend/.venv/bin/python
    backend/research/day8_final_tables.py` (Tables III/IV/V, Figs. 3–4);
    `./backend/.venv/bin/python backend/research/day10_figures.py` (Figs.
    1, 3–8); `cd research_paper && tectonic main.tex` (full paper, 21pp,
    0 undefined refs). Full table mapping every artifact to its command:
    `REPRODUCIBILITY.md`.

28. **Submission checklist**: `research/SUBMISSION_CHECKLIST.md` — 3
    unchecked items (page-count trim, affiliation placeholder, unified
    docker-compose), all with a named owner action; everything else
    (content integrity, reproducibility delivery, honest venue research,
    process integrity) verified true as of this report.
