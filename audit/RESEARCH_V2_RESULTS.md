# RESEARCH DISCOVERY V2 — final evaluation (pre-registered protocol)

Protocol: `evaluation/RESEARCH_EVALUATION_PROTOCOL.md`.
Files: `v2_eval_input.json`, `v2_eval_mapping.json`, `v2_eval_ratings.json`,
`V2_EVALUATION_RESULTS.md`.

## Methods and splits
A max |1m move|; B max recent anomaly; C frozen V1 score; D V2 triage. Same dates/FeatureSet/
anomaly/mechanism snapshot, theme-deduped. Fact cards use an identical schema; labels/scores/
hypotheses hidden; IDs globally shuffled. Independent LLM rater, four criteria 0–2.
Development: 2022-10-31, 2024-09-30. Validation: 2023-03-31. Test (held out): 2021-12-31.

## Final rater (48 objects)
| method | n | mean worthiness | P@3 | evidence suff. | falsifiability |
|---|---:|---:|---:|---:|---:|
| A max move | 12 | 0.875 | 0.00 | 0.17 | 1.25 |
| B max anomaly | 12 | 0.917 | 0.08 | 0.17 | 1.67 |
| C V1 score | 12 | **0.979** | **0.17** | 0.50 | 1.50 |
| D V2 triage | 12 | 0.833 | 0.00 | 0.25 | 1.50 |

Test split (D n=3, unlike the earlier exploratory run where n=1):

| method | n | mean | P@3 |
|---|---:|---:|---:|
| A | 3 | 0.833 | 0.00 |
| B | 3 | 0.583 | 0.00 |
| C | 3 | 0.583 | 0.00 |
| D | 3 | 0.750 | 0.00 |

**DISCOVERY VALUE: NOT VALIDATED.**
D is lower than C and B/A on the full sample and does not beat B/C on both mean and P@3 on the
test split (P@3 all zero). The earlier exploratory rating (D=1.350) did not replicate under the
second blind rater (D=0.833); this inter-rater instability is itself a failure of validation.
No weights were tuned after seeing either result.

## Why V2 failed (construct/criterion mismatch; not a code bug)
- The blind cards measure **asset selection worthiness**, not the V2 research question itself:
  hypotheses/falsifiers/decision-impact were hidden to keep methods blind. D's actual output was
  therefore not evaluated.
- D applies materiality/evidence gates before ranking; A/B/C do not. This confounds selection with
  ranking and makes P@3 not a like-for-like metric.
- Test split has only 3 D objects; no human labels; single LLM rater (two raters disagreed strongly).
- V2 still lacks consensus/options data; critical unknowns are declared but not resolved.
- The right next experiment is a common research-brief template for all methods, a common candidate
  pool with D-filter-only/random-within-pool baselines, multiple raters/human labels, and a frozen
  future window. This cannot be manufactured by changing thresholds.

## What V2 does add
Structured research candidates with >=2 competing hypotheses, evidence classified as fact/association/
unknown, critical unknowns, candidate-specific falsification tests, cost/decision impact, and an
ordinal priority rule (no hidden weighted sum). It is an audit-friendly research-question generator,
not a demonstrated improvement over simple baselines.
