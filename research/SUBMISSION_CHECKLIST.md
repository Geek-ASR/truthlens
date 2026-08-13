# Submission-Readiness Checklist

Status as of 2026-08-13 (Day 10). Checked items are verified true right
now, not aspirational; unchecked items are named, scoped gaps with an
owner action, not silently missing requirements.

## Content

- [x] Title, abstract, and contributions match what the experiments in
      Sections VII–XI actually support (Day 9 rewrite; no claim traces to
      nothing).
- [x] Every numeric claim traces to a versioned artifact under
      `research/` (Day 10 line-by-line audit; one real error found and
      fixed — a 6-vs-7 FALSE-item miscount inherited from a stale summary
      line in `GROUND_TRUTH.md`).
- [x] Headline negative finding (TruthLens underperforming Baseline 2 on
      the paired 6-item set) reported first and with equal-or-greater
      prominence than favorable results, per the governing protocol's own
      rule.
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
- [ ] **Page count: 21 pages against IEEE TPS's 10-page research-track
      limit (the best topical-fit venue found, Section "Venue" below).**
      Not trimmed in this pass (Day 10 self-audit, `DAY10_PEER_REVIEW.md`
      R3-4) because a mechanical cut risks reintroducing exactly the kind
      of error this same audit caught twice already. **Owner action**:
      a dedicated trim pass, ideally pairing every cut with a
      re-verification of the surrounding claim, not a word-count exercise
      alone. Candidate cuts already identified: tighten Related Work's
      six subsections into three-to-four; move the Section XIII
      claim-extraction-coverage caveat earlier into Section VII itself
      (subsuming, not duplicating, its Threats-to-Validity mention);
      shorten Taxonomy entries that already have full detail elsewhere
      (several entries are near-duplicates of prose already in Sections
      IX/X, kept in both places for the taxonomy's own scanability, which
      could be earned back with cross-references instead).
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
    passed; Round 2 (Aug 15, 2026) is 2 days from today and not
    realistically reachable given the remaining trim/polish work above.
    **The realistic target is this venue's 2027 cycle**, expected on a
    similar mid-year schedule.
  - **IEEE BigData 2026** — real, open deadline (Aug 21, 2026, 8 days
    out), Dec 14–17, 2026 in Phoenix, AZ — but a topical stretch (general
    big-data venue, no confirmed misinformation-specific track for 2026)
    and still an unrealistically tight timeline given the trim work
    above.
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
