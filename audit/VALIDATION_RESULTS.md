# VALIDATION RESULTS — rounds 1–2 (final)

## A. Data correctness (independent re-computation)

| Check | Before | After | Evidence |
|---|---|---|---|
| Monday return availability | SPY 2026-11-09 +2.37% had no 1d z | z=3.35 present | `FeatureBuilder` on real DB |
| CFTC as-of 2026-11-04 max date | 2026-11-07 (lookahead) | 2026-10-31 | positioning index |
| CFTC net/OI | −372,318 (raw) | −0.2048 (ratio) | POS_SP500_LEV |
| trend_break share | 1,181/2,935 = 40.2% | 93/1,506 = 5.6% | scan counters |
| Breadth | constant 0, 0 anomalies | 21 distinct values, 10 anomalies | US breadth series |
| Latest US bar | 2026-11-13 intraday (753.11) | dropped; last = 2026-11-12 | SPY price index |
| 3.213:1 share conversion | 520 rows quarantined | level_rebased, series continuous | price_data_issues |
| CPI YoY 2026-09 / 2026-10 | 4.00% / 3.91% (wrong) | 3.7377% / NaN | US_CPI YoY |
| Point-in-time Nikkei 2024-08-05 1m | −0.39% (replay leak) | −23.11% | slice_as_of |
| VIX 2024-08-05 1m | +2.29% (leak) | +209.05% | slice_as_of |
| ERP/CAPE availability | used unreleased CAPE | PIT-filtered macro only | code + test |

## B. Tests
- Offline: 137 passed (round 1: 121; baseline: 97), 9 network tests unchanged (run separately).
- New regression files: `test_time_semantics.py`, `test_readiness_handoff.py`,
  `test_status_lifecycle.py`, `test_data_integrity.py` (+7), `test_archetypes.py`,
  rollback + expectation-gap gate tests.

## C. Live scan (final, 2026-11-14)
- instruments: 125/125; prices 358,310; indicators 159,508 / 92 series.
- anomalies: 1,506 (trend_break 93; breadth 17; macro dated by availability; policy_rate_change 5).
- transmissions: 5 activated (M12 mixed 0.55, M05 mixed 0.14; M01/M09/M14 unsupported 0.05); p-values + BH-FDR applied per mechanism.
- opportunities: 11 = 2 watch, 3 low_priority, 2 invalidated, 4 excluded, **0 deep_research**.
  The absence of deep_research is a *result*: expectation proxies or mechanism evidence did not clear the
  explicit gates (gap≥0.15, confidence≥0.5, mechanism confidence≥0.40 + ≥2 FDR-significant tests).
- top research queue: DXY event revision (0.593) and Nikkei BoJ event (0.558);
  the 28-day-old SPY policy print is low_priority (0.603); DAX is no longer in the candidate pool after local SX5E/EUR drivers; a mechanism-breakdown candidate (USDJPY, 0.477) and
  one current VIX candidate invalidated by its own VIX3M condition (0.439).

## D. Historical cases (PIT slice per evaluation date)
Final after the detector-boundary fix and the stricter **case-entity** rule: **7/7** (COVID, 2022
rate shock, UK LDI, SVB, yen carry, China policy rally, gold vs real rates); report
`reports/validation_cases_20261114T092812Z.md`. The China case passes through the observed-policy-action
archetype (CSI 300, watch); SVB via credit_stress on the derived CREDIT_RISK series (HYG/IEF are case
assets); gold via the general **mechanism-breakdown** archetype ("gold vs real yields failed"), not a
case-specific rule. Mechanisms were often `unsupported` — correctly reported, not treated as detection failure.

## E. Handoff (investment-agent)
- Run executed; downstream process rc=0, but S8 returns `out_of_scope` (17 L2 views, 0 L1 facts,
  L3/L4 not produced). A records `semantic_status=refused`, task `not_completed:refused`,
  event `ia_research_not_completed`, CLI exit 2 — NOT success. Reason surfaced.
- Unit tests cover ok_valid / refused / rejected / insufficient_data / partial / missing artifact /
  stdout `ok:false`; a real `ok_valid` deep-research sample is still unavailable (B limitation).
