# Day 2 sourcing log — real attempt, tracked honestly

Per `DATASET_SPEC.md` and the precedent set by
`research_paper/benchmark/PROTOCOL.md` (which reported a ~8% Tier-1 hit
rate from checking 22 articles and found nothing new), every candidate
actually fetched and evaluated during this session is logged below,
hits and misses both — not just the successes.

## Result after two sourcing passes: 5 new Tier-1 items found, 7 candidates actively fetched and verified

Combined with the 2 pre-existing items from `PROTOCOL.md`, `items.jsonl`
now has **7 items total** — real progress toward the 20-30 target, not
yet there, reported as exactly what it is.

## Pass 2 (targeted at the two gaps pass 1 left open: non-provenance claim types, Hindi/Urdu content)

| # | Outlet | Article | Instagram embed found? | Live? | Outcome |
|---|---|---|---|---|---|
| 6 | BOOM Hindi | AI-generated/staged videos falsely linked to Assam floods | Yes, 2 URLs | Yes (checked both) | **HIT — item-0006.** Non-political-actor (disaster misinformation), closes the "all 5 items had a partisan actor" gap. |
| 7 | Alt News Hindi | BJP leader (Tajinder Bagga) shared clipped video of "Naara-e-Taqbeer" slogans at CJP protest | Yes, 1 URL | Yes | **HIT — item-0007.** First confirmed-Hindi-spoken-content item; first `misleading_context` (selective cropping, not fabrication or misidentification) claim type. |
| 8 | (search only, no article fetched) | `crore`/`lakh` statistic claims, BOOM/Alt News | Search returned no specific Instagram-embedded statistic fact-check | — | **NO HIT** — pure numeric/statistic claims did not surface a matching Instagram-specific fact-check this pass. |
| 9 | (search only) | PIB Fact Check financial-scheme deepfakes (Nirmala Sitharaman investment scheme) | Multiple candidates seen, none individually fetched/confirmed to have a specific Instagram (vs. X/WhatsApp) embed | — | **NOT PURSUED** — real backlog item, not a confirmed miss; needs a direct fetch to resolve either way. |
| 10 | (search only) | Global (Trump/US economy) fact-checks | Off-topic — search drifted to US politics despite Indian-outlet site filters | — | **NO HIT**, query design problem not a sourcing problem |
| 11 | (search only) | Factly + "statistics" + Instagram | Search did not surface Factly-specific results at all | — | **NO HIT** |

**Honest pattern observed, not yet confirmed as a real trend**: pure
statistic/numeric claims (a % figure, a budget number, an economic
indicator) are proving much harder to source from a *specific,
Instagram-embedded* fact-check than provenance/visual claims are —
plausibly because detailed statistical misinformation spreads more via
WhatsApp forwards and X screenshots (text-native platforms) than via
Instagram (a video/image-native platform), which would be a genuine,
citable finding about this dataset's domain if it holds up under more
searching, not just a search-skill problem. Flagged for the next
sourcing pass rather than assumed.

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

## Composition check against `DATASET_SPEC.md`'s diversity targets, at n=7 (after pass 2)

- Claim type spread: provenance ×4, visual ×1, event ×1, misleading_context
  ×1. Better than pass 1's all-provenance set, but **statistic, quote,
  law_policy, historical, and true_claim (a claim that just turns out to
  be straightforwardly accurate, framed as such from the start) are
  still entirely unrepresented.** This remains the dataset's biggest
  compositional gap.
- Verdict label spread: FALSE ×5, TRUE ×1, MISLEADING ×1. Still
  FALSE-heavy — a real, disclosed skew, not a target met. Professional
  fact-checkers publish far more "this is false" than "this is true"
  verdicts by the nature of what's newsworthy to debunk, so this skew
  may be a structural property of Tier-1 sourcing itself, not just a
  sampling gap this project can search its way out of — worth stating
  in the paper's dataset-construction discussion rather than treated as
  a temporary gap.
- Political actor spread: BJP ×2, Karni Sena, CJP, Delhi Police
  (government), Congress, none (disaster misinformation) — six distinct
  actors/institutions across 7 items. Good early diversity for RQ5,
  though n=7 is still far too small to support any bias conclusion.
- Language: 6 English, 1 Hindi (item-0007, confirmed via the fact
  -checker's own description of the spoken content, not just the
  caption). The Hindi/Urdu-mixed-transcript target is now **partially**
  met — one real item exists, but the project's stated target domain
  (English/Hindi/Urdu *mixed* transcripts, per the existing paper's own
  framing) isn't fully represented by a single monolingual-Hindi item;
  a genuinely code-switched item is still a gap.
