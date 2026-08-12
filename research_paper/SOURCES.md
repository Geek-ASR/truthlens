# Citation verification trail

Every entry in `references.bib` was found via a live web search or fetch
during drafting (August 2026), not recalled from training data. All 14
entries now have a fully confirmed title, author list, venue, and year,
each pulled via a direct `WebFetch` of the paper's own abstract/listing
page (not inferred from aggregated search-result summaries).

| BibTeX key | Verified via | Notes |
|---|---|---|
| thorne2018fever | Direct fetch, arxiv.org/abs/1803.05355 | |
| wang2017liar | Search cross-referenced with ACL Anthology P17-2067 | |
| hassan2017claimbuster | Search cross-referenced with kdd.org and author's own PDF | |
| chen2023frugalgpt | Direct fetch, arxiv.org/abs/2305.05176 | |
| deverna2025curatedcontext | Direct fetch, arxiv.org/abs/2511.18749 | |
| shang2021tiktec | Search cross-referenced with Illinois Experts repository | IEEE Xplore page itself did not return fetchable text (paywalled/JS-gated); page numbers not confirmed |
| vatndal2025shortcheck | Direct fetch, aclanthology.org/2025.ijcnlp-demo.9/ | Real title is "ShortCheck: ...", not the generic working title used in the first draft |
| peng2026partisan | Direct fetch, arxiv.org/abs/2412.16746 | |
| khajavi2026citecheck | Direct fetch, arxiv.org/abs/2605.27700 | |
| ovcharov2026oracle | Direct fetch (title/authors) + a second direct fetch of the full abstract, arxiv.org/abs/2606.00898 | See "A citation error caught and fixed" below |
| magesh2024hallucinationfree | Direct fetch, arxiv.org/abs/2405.20362 | See "A citation error caught and fixed" below |
| panchendrarajan2024claimdetection | Direct fetch, arxiv.org/abs/2401.11969 | |
| rahman2025hallucinationtotruth | Direct fetch, arxiv.org/abs/2508.03860 | |
| vykopal2024genaisurvey | Direct fetch, arxiv.org/abs/2407.02351 | |

## A citation error caught and fixed

The first draft cited a single paper (arXiv:2606.00898) for the claim
"legal-domain audits report that leading legal AI systems generate false
citations in 17-33% of responses." That number is real, but it comes from
a different paper — Magesh et al., "Hallucination-Free? Assessing the
Reliability of Leading AI Legal Research Tools" (arXiv:2405.20362,
Stanford RegLab, 2024), a preregistered, hand-scored evaluation of
commercial legal AI tools. arXiv:2606.00898 (Ovcharov, 2026) is a
different, later paper that is actually a *critique* of citation-grounding
oracles like the one behind that 17-33% style of measurement — it shows
the apparent hallucination rate such an oracle reports is highly sensitive
to the coverage of the citation graph it checks against, not just to the
model being measured (the same set of responses scored 15-21%
"hallucinated" against a sparse graph snapshot and under 1.1% against a
denser one built from the same underlying registry).

This was caught by directly fetching each paper's abstract when finishing
citation verification, rather than trusting the first-pass aggregated
search-result summary that had merged the two papers' subject matter. The
paper (`main.tex`) has been corrected: the 17-33% claim now cites Magesh
et al. correctly, and Ovcharov's paper is cited separately and accurately
in Section IV, for the point it actually makes — used as a direct caution
about a blind spot in TruthLens's own number-grounding check, since that
check has the same structural limitation (it can only verify a number
against sources the pipeline itself fetched, not against a number that is
real but supported only by a source it didn't retrieve).

This is exactly the class of error the paper argues LLM pipelines are
prone to (a plausible-sounding, almost-right citation), and it happened
during human-and-AI-assisted *paper writing about that exact failure
mode* — worth keeping in mind as a data point, not just a footnote.

## Before final submission

- `shang2021tiktec`'s page numbers are not yet confirmed (IEEE Xplore
  would not return fetchable page content).
- Re-verify all 14 entries once more immediately before submission in
  case any have been updated (arXiv preprints, several of which are from
  2026, may still be revised).
