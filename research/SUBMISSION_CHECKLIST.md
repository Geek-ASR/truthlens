# Submission-Readiness Checklist

Status as of 2026-08-13 (Day 10). Checked items are verified true right
now, not aspirational; unchecked items are named, scoped gaps with an
owner action, not silently missing requirements.

> **Updated, 2026-08-14**: items 16 and 36 below describe the pre-audit
> state and are corrected inline rather than left silently wrong — see
> `AUDIT_REPORT.md`/`RECONSTRUCTED_RESULTS.md` (baseline confound fixed,
> headline finding reversed) and `FINAL_REVISION_PLAN.md` (page-length
> trim, still short of the 10pp target but no longer at 21pp). All other
> items were re-checked against the current `main.tex` and remain
> accurate.

## Content

- [x] Title, abstract, and contributions match what the experiments in
      Sections VII–XI actually support (Day 9 rewrite; no claim traces to
      nothing).
- [x] Every numeric claim traces to a versioned artifact under
      `research/` (Day 10 line-by-line audit; one real error found and
      fixed — a 6-vs-7 FALSE-item miscount inherited from a stale summary
      line in `GROUND_TRUTH.md`).
- [x] **(2026-08-14 update)** The headline finding changed: a
      skeptical post-submission audit found and fixed a real
      claim-input confound in Baselines 1–3 (`AUDIT_REPORT.md`), and
      corrected, full TruthLens now beats 2 of 3 baselines rather than
      trailing 2 of 3 (`RECONSTRUCTED_RESULTS.md`). The correction is
      reported with the same discipline this item originally checked
      for: Section VII leads with the methodological fix itself, before
      the corrected number, with the same or greater prominence than a
      flattering result would have gotten.
- [x] No fabricated datasets, sources, experiments, or benchmark scores
      (nothing in this program was generated without a real, live run
      behind it — confirmed across Days 1–10, including this pass's own
      two newly-found and fixed bugs, which is itself evidence the checks
      are real rather than pro forma).
- [x] `RESEARCH_FAILED` vs. `UNVERIFIED` distinction maintained
      throughout; no claim-coverage failure is presented as a successful
      fact-check.
- [x] No hallucination-rate claim without human annotation behind it;
      "grounding-constraint violation rate" / "unsupported generation
      rate" terminology used consistently (Rule 8).
- [x] Political neutrality is not claimed as an established property —
      RQ5 is explicitly deferred, not asserted resolved.
- [x] Visual-misinformation-detection capability is not claimed —
      Section X states plainly that TruthLens has no reverse-image/video
      -search capability and has never claimed one.
- [ ] **(2026-08-14 update) Page count: 20 pages total, Appendix begins
      on page 17, against IEEE TPS's 10-page research-track limit (the
      best topical-fit venue found, Section "Venue" below) — improved
      from 21pp (pre-audit) / 24pp (post-audit, pre-trim), still not
      met.** A 2026-08-14 trim pass moved the full failure-mode taxonomy,
      the superseded baseline table, and several evidence-quality
      deep-dive subsections into a new Appendix (excluded from IEEE
      TPS's page count by its own rules) and tightened prose throughout
      every section — the exact candidate cuts this item used to list
      (Related Work condensed, Taxonomy moved out of the counted body)
      are now done; see `FINAL_REVISION_PLAN.md` for what's left.
      **Owner action**: closing the remaining gap needs either moving
      genuinely central content out of the counted body (the
      support-validity construct, cross-post attribution problem,
      four-way evidence metric — each flagged as a real strength by
      `IEEE_REVIEW.md`) or retargeting a venue with a larger page
      budget, per that review's own recommendation.
- [ ] Author affiliation is a visible `TODO` placeholder, not a guess
      (correct behavior for this drafting context) — **owner action**:
      Aditya fills in before any real submission.

## Reproducibility

- [x] `research/environment.lock` committed (130 pinned packages).
- [x] Two git tags mark the dataset/code freeze points
      (`truthlens-pre-ieee`, `truthlens-day8-frozen`); a third
      (`truthlens-day9-general-fixes`) now marks the post-freeze
      validator/vision-context fixes' exact commit.
- [x] Every table and figure has a documented regeneration command
      (`REPRODUCIBILITY.md`), verified against the actual compiled PDF's
      figure numbers, not assumed from generation-order filenames (a real
      mismatch was found and fixed this pass).
- [x] Full test suite passes (161/161, `backend/.venv/bin/python -m
      pytest -q`, confirmed today).
- [x] Two disclosed, real reproducibility gaps stated explicitly, not
      hidden: Fig. 6's $n=68$ tier/stance distribution needs a live
      Postgres instance not running in every environment; several
      validator/multimodal figures hardcode published human-judgment
      counts that are not machine-derivable from a formula.
- [ ] No unified `docker-compose up` for Postgres+MinIO+Ollama with
      models pre-pulled. **Owner action**: containerize Ollama + a model
      -pull step, or explicitly scope this as "not attempted" in the
      paper's own reproducibility statement if submitting before it's
      built.
- [ ] LLM sampling is unseeded — genuinely re-running any experiment
      end-to-end may not reproduce the exact same numbers, only the
      exact same *arithmetic over already-saved numbers*. This is now
      explicitly disclosed (`REPRODUCIBILITY.md`'s "regeneratable ≠
      re-runnable" section) rather than left implicit — no further action
      needed unless seeding becomes technically necessary for a specific
      future venue's requirements.

## Venue

- [x] Real candidate venues researched and verified live (not
      fabricated), with actual deadlines and page limits as of
      2026-08-13:
  - **IEEE TPS 2026** ("Trust, Privacy and Security in Intelligent
    Systems") — best topical fit (`"Trust in social media -- AI-enabled
    disinformation and misinformation at scale"` is an explicit named
    topic); 10-page research track, standard IEEE two-column, anonymized
    submission required. Round 1 deadline (June 15, 2026) has already
    passed; **Round 2 (Aug 15, 2026) is now 1 day away (checked
    2026-08-14)** and not realistically reachable given the remaining
    trim/polish work above and the still-unmet page limit.
    **The realistic target is this venue's 2027 cycle**, expected on a
    similar mid-year schedule.
  - **IEEE BigData 2026** — real, open deadline (Aug 21, 2026, **7 days
    out as of 2026-08-14**), Dec 14–17, 2026 in Phoenix, AZ — but a
    topical stretch (general big-data venue, no confirmed
    misinformation-specific track for 2026) and still an unrealistically
    tight timeline given the trim work above.
  - **MisD (Misinformation Detection in the Era of LLMs) @ ICWSM** —
    excellent topical fit (LLM-based misinformation detection
    specifically), but the 2026 edition already occurred (May 26, 2026,
    Los Angeles); realistic target is the next edition once announced.
  - **FEVER workshop @ EACL/ACL** and **CLEF CheckThat! Lab** — both
    excellent topical fits (fact-checking specifically), both had 2026
    -cycle deadlines that already passed (EACL 2026's workshop deadlines
    were Dec 2025–Jan 2026; CLEF-2026 CheckThat!'s overview paper is
    already published, meaning that cycle closed). Realistic target is
    each venue's next (2027) cycle once dates publish.
  - **Assessment, stated plainly**: no real, currently-open venue with
    both strong topical fit and a genuinely reachable deadline exists as
    of this writing. This is reported honestly rather than forcing a
    rushed submission to whichever deadline happens to still be open.
- [ ] **Owner action**: decide between (a) targeting IEEE TPS 2027 or the
      next MisD/FEVER/CheckThat! cycle once announced (recommended — best
      topical fit, realistic timeline for the trim work above), or
      (b) rushing IEEE BigData 2026's Aug 21 deadline at real cost to
      polish quality. Not decided in this pass — a genuine choice only
      Aditya can make, since it trades off speed against topical fit and
      the trim-pass quality this checklist itself recommends.

## Process integrity

- [x] Two real bugs found and fixed during Day 10 preparation itself
      (`day8_final_tables.py`'s variable-shadowing bug;
      `GROUND_TRUTH.md`'s 6-vs-7 miscount), both disclosed in the paper's
      own taxonomy/text rather than silently corrected.
- [x] Three-reviewer self-audit completed with real, adversarial
      criticism, not a formality (`DAY10_PEER_REVIEW.md`) — 13 concerns
      raised, 4 fixed, 9 recorded open with reasons.
- [x] No result was tuned on the held-out test set; the two general
      fixes made in response to the headline finding are
      ground-truth-independent, with the one place that's imperfect (the
      new validator check's phrase-list calibration) disclosed as a named
      threat to validity, not hidden.
