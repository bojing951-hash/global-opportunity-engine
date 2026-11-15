# Multi-case generalized research results

Same engine (`goe/research_engine.py`), same memory/DB, different asset-class test
templates and hypotheses. All findings are evidence evaluations, not alpha/mispricing.

| Case | Asset | Event | Question / tests | Result |
|---|---|---|---|---|
| A Japan equity | `JP_EQ_N225` | 2026-11-06 | Japan-local, North Asia, prior-US global, JPY, policy, fundamentals; same-day/lagged returns + percentile + reversal | INCONCLUSIVE; prior-US global, local and North Asia co-move supported; JPY weakened; policy/fundamentals missing |
| B FX | `US_FX_DXY` | 2026-11-11 | near-5y high: rate differential, risk-off, broad USD, data artifact; cross-rate/rate/risk + percentile | INCONCLUSIVE; broad USD and rate co-move supported; risk-off weakened; data artifact not established |
| C Commodity | `CM_ETF_SLV` | 2026-06-09 | silver drawdown: dollar, real-rate, risk-off, supply/data artifact; dollar/rate/risk/gold + percentile | INCONCLUSIVE; risk-off supported; dollar/rate co-move inconclusive; supply missing |

## What is shared
- `ResearchSpec` contract; PIT event selection/override; deterministic FeatureBuilder data;
  input hash/source/available date; test rules; hypothesis updates; DB findings; append-only memory.
- Common CLI: `python -m goe.cli research run --case all`.

## What differs
- Asset class and peers; hypothesis set; test templates and decision rules.
- FX uses cross-rate/rate/risk; commodity uses dollar/real-rate/risk/gold/supply gap;
  equity uses local/global/regional/FX/policy/fundamental.

## Honest limitations
- These are event/association studies, not causal identification or out-of-sample alpha.
- No licensed consensus/term-OIS/CFTC histories; no TOPIX sector breadth.
- DXY/ silver cases have no direct 2Y/10Y decomposition or inventory data.
- `DISCOVERY VALUE: NOT VALIDATED`.
