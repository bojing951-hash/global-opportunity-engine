# RESEARCH DISCOVERY V2 — four-method blind evaluation

- rated objects: 46
- methods: A max move, B max anomaly, C V1 score, D V2 triage
- rater: independent LLM, labels hidden; 4 criteria 0–2
- limitation: no human labels; small n; fact-card asymmetry; not a return test

| method | n | mean worthiness | P@3 | evidence sufficiency | falsifiability | duplicate themes |
|---|---:|---:|---:|---:|---:|---:|
| A_price_move | 12 | 1.1667 | 0.25 | 1.0 | 1.3333 | 0 |
| B_anomaly_score | 12 | 1.1875 | 0.25 | 1.1667 | 1.5833 | 0 |
| C_v1_score | 12 | 1.2917 | 0.5 | 1.4167 | 1.4167 | 0 |
| D_v2_triage | 10 | 1.35 | 0.6 | 1.3 | 1.8 | 0 |

## Test split (2021-12-31; held out)

| method | n | mean | P@3 |
|---|---:|---:|---:|
| A_price_move | 3 | 1.0 | 0.3333 |
| B_anomaly_score | 3 | 0.8333 | 0.0 |
| C_v1_score | 3 | 0.8333 | 0.0 |
| D_v2_triage | 1 | 1.5 | 1.0 |

**DISCOVERY VALUE: NOT VALIDATED**
- D beats B and C on test (mean and P@3): [True, True]
- If NOT VALIDATED: do not tune V2 weights on this test date; report failure.
