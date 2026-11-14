# RESEARCH DISCOVERY V2 — four-method blind evaluation

- rated objects: 12
- methods: A max move, B max anomaly, C V1 score, D V2 triage
- rater: independent LLM, labels hidden; 4 criteria 0–2
- limitation: no human labels; small n; fact-card asymmetry; not a return test

| method | n | mean worthiness | P@3 | evidence sufficiency | falsifiability | duplicate themes |
|---|---:|---:|---:|---:|---:|---:|
| A_price_move | 3 | 1.0833 | 0.0 | 1.3333 | 1.0 | 0 |
| B_anomaly_score | 3 | 0.9167 | 0.0 | 1.0 | 1.0 | 0 |
| C_v1_score | 3 | 1.5 | 0.6667 | 1.6667 | 1.3333 | 0 |
| D_v2_triage | 3 | 1.0 | 0.0 | 1.0 | 1.0 | 0 |

## Test split

| method | n | mean | P@3 |
|---|---:|---:|---:|
| A_price_move | 3 | 1.0833 | 0.0 |
| B_anomaly_score | 3 | 0.9167 | 0.0 |
| C_v1_score | 3 | 1.5 | 0.6667 |
| D_v2_triage | 3 | 1.0 | 0.0 |

**DISCOVERY VALUE: NOT VALIDATED**
- D beats B and C on test (mean and P@3): [False, False]
- If NOT VALIDATED: do not tune V2 weights on any reused date; report failure.
