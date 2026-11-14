# RESEARCH DISCOVERY V2 — final evaluation (pre-registered protocol)

Protocol: `evaluation/RESEARCH_EVALUATION_PROTOCOL.md`.
Files: `v2_eval_input.json`, `v2_eval_mapping.json`, `v2_eval_ratings.json`,
`V2_EVALUATION_RESULTS.md`.

## Methods and splits
A max |1m move|; B max recent anomaly; C frozen V1 score; D V2 triage. Same dates/FeatureSet/
anomaly/mechanism snapshot, theme-deduped. Fact cards use an identical schema; labels/scores/
hypotheses hidden; IDs globally shuffled. Independent LLM rater, four criteria 0–2.
Development/exploratory: 2022-10-31, 2023-03-31, 2024-09-30, 2021-12-31 (reused; no independent test).

## Final rater (48 objects; exploratory, no independent test)
| method | n | mean worthiness | P@3 | evidence suff. | falsifiability |
|---|---:|---:|---:|---:|---:|
| A max move | 12 | 0.875 | 0.00 | 0.17 | 1.25 |
| B max anomaly | 12 | 0.917 | 0.08 | 0.17 | 1.67 |
| C V1 score | 12 | **0.979** | **0.17** | 0.50 | 1.50 |
| D V2 triage | 12 | 0.833 | 0.00 | 0.25 | 1.50 |

The 2021-12-31 date was used in a first V2 run, then V2's gates changed and the same date was
reused. It is therefore **exploratory/reused**, not an independent test. No independent test split
remains. Accordingly:

**DISCOVERY VALUE: NOT VALIDATED.**

Even on the reused date, D (0.750) did not beat A (0.833) and P@3 was zero for every method. On the
full sample D is below C and B/A. The earlier exploratory rater gave D 1.350; the final rater gave
0.833 — inter-rater instability is itself a validation failure. No weights were tuned on the reused
date.

## Why V2 failed (construct/criterion mismatch; not a code bug)
- The blind cards measure **asset selection worthiness**, not the V2 research question itself:
  hypotheses/falsifiers/decision-impact were hidden to keep methods blind. D's actual output was
  therefore not evaluated.
- D applies materiality/evidence gates before ranking; A/B/C do not. This confounds selection with
  ranking and makes P@3 not a like-for-like metric.
- The reused 2021 date has only 3 D objects; no human labels; single LLM rater (two raters disagreed strongly).
- V2 still lacks consensus/options data; critical unknowns are declared but not resolved.
- The right next experiment is a common research-brief template for all methods, a common candidate
  pool with D-filter-only/random-within-pool baselines, multiple raters/human labels, and a frozen
  future window. This cannot be manufactured by changing thresholds.

## What V2 does add
Structured research candidates with >=2 competing hypotheses, evidence classified as fact/association/
unknown, critical unknowns, candidate-specific falsification tests, cost/decision impact, and an
ordinal priority rule (no hidden weighted sum). It is an audit-friendly research-question generator,
not a demonstrated improvement over simple baselines.
