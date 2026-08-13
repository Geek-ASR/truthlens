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

## Real ingestion status (Day 4, 2026-08-13)

All 7 items were run through the actual system's ingestion pipeline
(fetch + transcribe + OCR + vision) for `research/MULTIMODAL_EVALUATION.md`.
Result: **6 of 7 fetchable**, one real, persistent failure:

- **item-0003**: Instagram consistently returns an empty media response
  to yt-dlp for this specific post — confirmed on 2 independent
  attempts, each internally retried 3× with backoff, both attempts
  failing identically. Not resolved. May be genuinely transient
  (worth a later retry) or may indicate this specific post has become
  harder to fetch since it was added to the dataset on 2026-08-13 —
  can't distinguish from the evidence available. **Excluded from Day
  4's claim-coverage measurement** rather than scored as a coverage
  failure, since there is no real content to extract claims from.
- **item-0005**: initially failed for a different, real reason — a code
  bug (see below), not an Instagram-side issue. Now fixed and
  ingesting successfully.

## Pass 3 (2026-08-13, growing the dataset before Day 8 per explicit direction)

Targeted at RQ5's matched-pair gap (`BIAS_CALIBRATION_EFFICIENCY.md`)
and the still-missing `quote`/`law_policy`/`historical` claim types.

| # | Outlet | Article | Instagram embed found? | Live? | Outcome |
|---|---|---|---|---|---|
| 12 | Alt News | Bihar education minister Mithilesh Tiwari "girls don't need education" | Yes, 1 URL (@aamaadmiparty) | Yes | **HIT — item-0008.** First `quote`-type item (audio-transcript word misrepresentation: "agitation" misheard/misreported as "education"), not provenance/visual. Real cross-party amplification (AAP source post, amplified by Indian Youth Congress, an India TV anchor, and a former Deputy CM) — the closest thing to a multi-actor case in the dataset so far, though not a controlled matched pair. |
| 13 | Alt News | BJP leaders share old Patna video as CJP-protest hydrogen-train vandalism | Yes, 1 URL (@drsudhanshutrivedibjp) | Yes | **HIT — item-0009.** Second BJP item (alongside item-0001), same "old video recontextualized" template — adds within-actor volume, not a cross-actor match. |
| 14 | Factly | PM Modi did not announce a free smartphone scheme (AI voice-cloned video) | Yes, 2 URLs found in article HTML | **No** — both URLs returned HTTP 200 but with no Open Graph metadata at all (unlike every other live post checked this project), consistent with the article's own phrasing ("archived versions... can be found here") implying the originals are no longer normally accessible | **NO HIT** — a real, well-documented `law_policy`-type case (AI-voice-cloned claim about a government scheme) that could not be used because the specific posts are gone. Real, disclosed miss, not silently dropped. |
| 15 | Alt News | Photo falsely claimed as Bhagat Singh/Sukhdev/Rajguru's last rites | No Instagram URL in article (Facebook only); also predates this project's 2026 window (published 2021) | — | **NO HIT** — real `historical`-type candidate, wrong platform and too old |
| 16 | Alt News | Morphed Mountbatten letter claiming RSS didn't join the anti-British movement | No Instagram URL in article (X/Twitter only) | — | **NO HIT** — real `historical`-type candidate, wrong platform |

**Pattern reinforced**: `historical` and `law_policy` claim types continue
to concentrate on X/Facebook/WhatsApp rather than Instagram specifically
in this project's searches so far (3 real candidates checked this pass,
0 had a usable Instagram embed) — consistent with, and now a second
data point for, pass 2's hypothesis about `statistic` claims. Worth
stating as a likely genuine property of Instagram as a misinformation
vector for this domain (more visual/video-native, less
text-document-native) rather than a continued search failure, though
still not proven at this sample size.

Dataset after pass 3: **9 items** (up from 7). Composition update: claim
types now {provenance: 5, visual: 1, event: 1, misleading_context: 1,
quote: 1} — `statistic`, `law_policy`, `historical`, `true_claim` remain
unrepresented. Political actors: {BJP: 3, Karni Sena: 1, CJP: 1, Delhi
Police: 1, Congress: 1, AAP: 1, none: 1} — BJP now has 3 items (still no
controlled matched pair against another single actor on the same
topic/structure; RQ5 remains blocked for the reasons already stated in
`BIAS_CALIBRATION_EFFICIENCY.md`).

**A real bug found and fixed via this dataset, not just documented**:
item-0005 (a genuine photo post) failed with yt-dlp reporting `"No
video formats found!"` — correct information, but
`app/services/url_downloader.py`'s existing photo-post fallback only
matched the substring `"no video in this post"`, a different phrasing.
Fixed by matching a tuple of known "no video" phrasings instead of one
fixed string (same pattern already used for `_RETRYABLE_MESSAGES` one
function over). Two new regression tests added; re-verified live
immediately after the fix. See `research/MULTIMODAL_EVALUATION.md` for
full detail and `backend/tests/test_url_downloader_photo_fallback.py`
for the tests.

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
