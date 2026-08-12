# Day 2 sourcing log — real attempt, tracked honestly

Per `DATASET_SPEC.md` and the precedent set by
`research_paper/benchmark/PROTOCOL.md` (which reported a ~8% Tier-1 hit
rate from checking 22 articles and found nothing new), every candidate
actually fetched and evaluated during this session is logged below,
hits and misses both — not just the successes.

## Result: 3 new Tier-1 items found, 5 candidates actively fetched and verified

Combined with the 2 pre-existing items from `PROTOCOL.md`, `items.jsonl`
now has **5 items total** — real progress toward the 20-30 target, not
yet there, reported as exactly what it is.

## Candidates actively fetched (article content + liveness of the Instagram URL both checked)

| # | Outlet | Article | Instagram embed found? | Live (HTTP 200, real og:tags)? | Outcome |
|---|---|---|---|---|---|
| 1 | BOOM | Sexualised AI Fakes Replace Real CJP Protesters | Yes, 4 URLs | Yes (checked all 4) | **HIT — item-0003** |
| 2 | Alt News | Baton-with-nails... (the `@ansh.visuals_` telling) | Yes, but post confirmed made unavailable in India ~6:40pm July 21 2026 | N/A — not fetchable | **NO HIT** — real, findable claim, but not usable since TruthLens itself could not fetch it. Led to candidate #3. |
| 3 | BOOM | Batons With Nails: Delhi Police Calls Real CJP Protest Video 'Fake' (same event, different original poster) | Yes, 1 URL (@gaur_95_com) | Yes | **HIT — item-0004** |
| 4 | Alt News | No, Piyush Goyal did not call for hanging 'cockroaches' (deepfake) | **No** — viral spread was on X/Twitter, not Instagram | N/A | **NO HIT** — genuinely doesn't qualify for this Instagram-scoped dataset, not a quality problem with the fact-check itself |
| 5 | Factly | Video of Abhijeet Dipke with Maharashtra Congress leader falsely shared as Jharkhand Congress president | Yes, multiple URLs; used the genuine original (`@babajanidurrani`) | Yes | **HIT — item-0005** |

## Candidates seen in search results but not yet individually fetched/verified (real backlog for the next sourcing pass, not silently dropped)

- BOOM: "Sonam Wangchuk's Visit To Pakistan" (Amit Malviya/NSA claim)
- BOOM: "Cropped Video Falsely Shared As CJP Protesters Raising Islamic Slogans" (deprioritized this pass: topical overlap risk — already have 3 CJP-protest-adjacent items; a 4th would over-concentrate the sample)
- Alt News: "J P Nadda got down from PM Modi's car" claim
- Alt News: "Jyotiraditya Scindia's election rally faux pas" (old video recirculated)
- BOOM: "Manmohan Singh and Sonia Gandhi Switching Seats"
- Alt News: "Congress leaders shared edited video... Chitra Tripathi" (Alka Lamba, Ragini Nayak)
- Alt News: "Fictional Congress MLA Anil Upadhyay" video
- Alt News: "Rahul Gandhi's photo on sanitary pads" (Congress FIR)
- Alt News: "Rahul Gandhi greeting differently-abled person" (misleading claim by Amit Malviya)
- Factly: "The woman who threw slippers at the Shivaji Maharaj statue... is not Muslim" — real candidate for a person-misidentification/communal-misinformation category, not yet checked for Instagram embed
- Factly: several old-video-miscaptioned items (Nepal unrest, Assam floods, plane turbulence) — likely provenance-type hits but not yet checked for a specific still-live Instagram embed vs. other platforms

## Honest observation on hit rate this session vs. `PROTOCOL.md`'s historical ~8%

3 hits out of 5 actively-fetched candidates this session is a much
higher rate than the ~8% (2/26) `PROTOCOL.md` reported. The likely
reason, stated as a hypothesis not a proven cause: this session
targeted very recent (July-August 2026), explicitly Instagram-tagged,
high-profile political fact-checks (CJP protest coverage specifically),
which is a period and topic cluster with unusually dense fact-checker
attention — not necessarily representative of the general hit rate
going forward. The next sourcing pass should test this by deliberately
checking older (pre-July 2026) and lower-profile candidates from the
backlog above, to see if the rate holds or reverts toward `PROTOCOL.md`'s
figure. Reported here rather than assumed, per Rule 1.

## Composition check against `DATASET_SPEC.md`'s diversity targets, at n=5

- Visual/provenance items: 5 of 5 (all items so far are provenance-type
  misinformation — real footage/photo, wrong context or wrong
  identification). **This is a real, disclosed skew**, not a target met:
  the dataset needs non-provenance claim types too (statistic, quote,
  law/policy, historical) to test claim coverage on ordinary spoken/
  transcript claims, not only visual ones. Next sourcing pass should
  prioritize this gap over more provenance items.
- Verdict label spread: FALSE ×3 (item-0001, 0002, 0003), TRUE ×1
  (item-0004), MISLEADING ×1 (item-0005). Meaningfully more balanced
  than the original 2-item all-FALSE set.
- Political actor spread: BJP, Karni Sena, CJP, Delhi Police
  (government), Congress — five distinct actors/institutions across 5
  items, no repeats. Good early diversity for RQ5, though n=5 is far too
  small to support any bias conclusion yet.
- Language: all 5 items are English-language posts/captions (even where
  the broader event involves Hindi-speaking participants). The
  Hindi/Urdu-mixed-transcript target from `DATASET_SPEC.md` is **not yet
  met** and is a real gap for the next pass — English-language political
  Instagram content was simply what this session's searches surfaced
  first.
