# RESEARCH DISCOVERY V2 — evaluation outcome (pre-registered protocol)

Protocol: `evaluation/RESEARCH_EVALUATION_PROTOCOL.md`.
Input/mapping/ratings: `evaluation/v2_eval_input.json`, `v2_eval_mapping.json`,
`v2_eval_ratings.json`; generated results: `evaluation/V2_EVALUATION_RESULTS.md`.

## What was compared
A = max |1m price move|; B = max recent anomaly; C = frozen V1 score; D = V2 triage.
Same as-of dates, same FeatureSet/anomaly/mechanism snapshot, same theme dedupe. Fact cards are
identical in schema; method labels/scores/hypotheses hidden; IDs globally shuffled. Independent LLM
rater scored four criteria 0–2.

## Results (descriptive, not a return test)
| method | n | mean worthiness | P@3 | evidence sufficiency | falsifiability |
|---|---:|---:|---:|---:|---:|
| A max move | 12 | 1.167 | 0.25 | 1.00 | 1.33 |
| B max anomaly | 12 | 1.188 | 0.25 | 1.17 | 1.58 |
| C V1 score | 12 | 1.292 | 0.50 | 1.42 | 1.42 |
| **D V2 triage** | **10** | **1.350** | **0.60** | 1.30 | **1.80** |

D is descriptively highest on worthiness/P@3/falsifiability; evidence sufficiency is slightly below
C. D has fewer selected objects because V2 intentionally returns only researchable/gated candidates
(10 vs 12), not because of a fixed top-3 fill.

## Held-out test (2021-12-31)
A 1.00 / 0.33, B 0.83 / 0.00, C 0.83 / 0.00, D 1.50 / 1.00. D wins both metrics, **but n=1**.
The pre-registered decision rule requires n>=3; therefore:

**DISCOVERY VALUE: NOT VALIDATED.**

We do not add test dates after seeing this result, and we do not tune V2 rules on the test date.
The descriptive advantage is hypothesis-generating only. A future evaluation needs a larger truly
held-out sample and, ideally, human/expert labels; only then can `VALIDATED` be claimed.

## Failure modes / limits
- Single LLM rater, no human labels; 4 criteria are a proxy for research value.
- D's cards are mechanism-rich because D selects mechanism-linked objects (method-fact asymmetry).
- No measurement of research time saved or unsupported-claim rate; not fabricated.
- Test n=1 is the binding limitation; n<3 makes the decision rule fail regardless of point estimates.
- V2 still cannot access consensus/options data; critical unknowns are declared, not resolved.
