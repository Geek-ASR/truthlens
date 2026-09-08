# TruthLens local-only configuration -- validation-split evaluation

- Corpus: v2 `validation` split, 193 items
- Rows in `local_eval_v2.jsonl`: 193
- Configuration: `full_truthlens_local` -- every stage on local llama3.2, DuckDuckGo keyless search, no Gemini escalation, no API keys, $0.

## Outcome distribution

| outcome_type | n | share of scored |
|---|--:|--:|
| resolved | 67 | 34.7% |
| no_verifiable_claims | 126 | 65.3% |
| research_failed | 0 | 0.0% |
| error | 0 | 0.0% |

## Headline verdict accuracy (bucketed, resolved items only)

- **Accuracy = 20/67 = 29.9%**  (Wilson 95% CI [20.2%, 41.7%])
- **Balanced accuracy (mean per-bucket recall) = 22.2%**
- Majority-class baseline (always predict FALSE) = 85.1%  (balanced accuracy 33.3%)

## Confusion matrix (ground-truth bucket x predicted bucket, resolved items)

| GT \ pred | FALSE | MISLEADING | TRUE | UNVERIFIED | row total |
|---|--:|--:|--:|--:|--:|
| **FALSE** | 19 | 1 | 10 | 27 | 57 |
| **MISLEADING** | 4 | 0 | 1 | 2 | 7 |
| **TRUE** | 1 | 1 | 1 | 0 | 3 |

## Per-class F1 over the full label set (resolved items)

| label | precision | recall | F1 | support (GT) |
|---|--:|--:|--:|--:|
| TRUE | 0.200 | 0.333 | 0.250 | 3 |
| MOSTLY_TRUE | 0.000 | 0.000 | 0.000 | 0 |
| MISLEADING | 0.000 | 0.000 | 0.000 | 7 |
| MOSTLY_FALSE | 0.000 | 0.000 | 0.000 | 0 |
| FALSE | 0.800 | 0.211 | 0.333 | 57 |
| UNVERIFIED | 0.000 | 0.000 | 0.000 | 0 |

- **Macro-F1 (over 3 GT-present classes) = 0.194**

## Abstention and infrastructure outcomes

- Abstention rate (UNVERIFIED / resolved) = 29/67 = 43.3%
- False-abstention rate ((UNVERIFIED resolved + no_verifiable_claims) / scored, every GT label is confident) = 155/193 = 80.3%
- Research-failed rate = 0/193 = 0.0%
- Errored items = 0

## Accuracy by platform (resolved items)

| platform | n resolved | correct | accuracy |
|---|--:|--:|--:|
| facebook | 7 | 4 | 57.1% |
| instagram | 6 | 1 | 16.7% |
| x | 54 | 15 | 27.8% |

## Accuracy by ground-truth label (resolved items)

| ground-truth label | n resolved | correct | accuracy |
|---|--:|--:|--:|
| FALSE | 57 | 19 | 33.3% |
| MISLEADING | 7 | 0 | 0.0% |
| TRUE | 3 | 1 | 33.3% |

## Accuracy by language (resolved items)

| language | n resolved | correct | accuracy |
|---|--:|--:|--:|
| bn | 2 | 0 | 0.0% |
| en | 53 | 16 | 30.2% |
| hi | 12 | 4 | 33.3% |

## Accuracy by vision_context_available (resolved items)

| vision_context_available | n resolved | correct | accuracy |
|---|--:|--:|--:|
| False | 38 | 12 | 31.6% |
| True | 29 | 8 | 27.6% |

## Accuracy by annotation_status (resolved items)

| annotation_status | n resolved | correct | accuracy |
|---|--:|--:|--:|
| (pre-protocol) | 8 | 2 | 25.0% |
| needs_review | 3 | 1 | 33.3% |
| reviewed | 56 | 17 | 30.4% |

