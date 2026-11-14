# RESEARCH DISCOVERY V2 — four-method blind evaluation

- rated objects: 48
- methods: A max move, B max anomaly, C V1 score, D V2 triage
- rater: independent LLM, labels hidden; 4 criteria 0–2
- limitation: no human labels; small n; fact-card asymmetry; not a return test

| method | n | mean worthiness | P@3 | evidence sufficiency | falsifiability | duplicate themes |
|---|---:|---:|---:|---:|---:|---:|
| A_price_move | 12 | 0.875 | 0.0 | 0.1667 | 1.25 | 0 |
| B_anomaly_score | 12 | 0.9167 | 0.0833 | 0.1667 | 1.6667 | 0 |
| C_v1_score | 12 | 0.9792 | 0.1667 | 0.5 | 1.5 | 0 |
| D_v2_triage | 12 | 0.8333 | 0.0 | 0.25 | 1.5 | 0 |

## Test split (2021-12-31; held out)

| method | n | mean | P@3 |
|---|---:|---:|---:|
| A_price_move | 3 | 0.8333 | 0.0 |
| B_anomaly_score | 3 | 0.5833 | 0.0 |
| C_v1_score | 3 | 0.5833 | 0.0 |
| D_v2_triage | 3 | 0.75 | 0.0 |

**DISCOVERY VALUE: NOT VALIDATED**
- D beats B and C on test (mean and P@3): [False, False]
- If NOT VALIDATED: do not tune V2 weights on this test date; report failure.
