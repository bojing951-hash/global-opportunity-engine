# VALIDATION RESULTS — round 1 (draft, updated after final scan)

## A. Data correctness (independent re-computation)

| Check | Before | After | Evidence |
|---|---|---|---|
| Monday return availability | SPY 2026-11-09 +2.37% had no 1d z | z=3.35 present | `FeatureBuilder` on real DB |
| CFTC as-of 2026-11-04 max date | 2026-11-07 (lookahead) | 2026-10-31 | positioning index |
| CFTC net/OI | −372,318 (raw) | −0.2048 (ratio) | POS_SP500_LEV |
| trend_break share | 1,181/2,935 = 40.2% | 134/1,651 = 8.1% | scan counters |
| Breadth | constant 0, 0 anomalies | 21 distinct values, 10 anomalies | US breadth series |
| Latest US bar | 2026-11-13 intraday (753.11) | dropped; last = 2026-11-12 | SPY price index |
| 3.213:1 share conversion | 520 rows quarantined | level_rebased, series continuous | price_data_issues |
| CPI YoY 2026-09 / 2026-10 | 4.00% / 3.91% (wrong) | 3.7377% / NaN | US_CPI YoY |
| Point-in-time Nikkei 2024-08-05 1m | −0.39% (replay leak) | −23.11% | slice_as_of |
| VIX 2024-08-05 1m | +2.29% (leak) | +209.05% | slice_as_of |
| ERP/CAPE availability | used unreleased CAPE | PIT-filtered macro only | code + test |

## B. Tests
- Offline: 121 passed (was 97), 9 network tests unchanged (run separately).
- New regression files: `test_time_semantics.py`, `test_readiness_handoff.py`,
  `test_status_lifecycle.py`, `test_data_integrity.py` (+7), `test_archetypes.py`,
  rollback + expectation-gap gate tests.

## C. Live scan (final, 2026-11-14)
- instruments: 125/125; prices 358,310; indicators 159,508 / 92 series.
- anomalies: 1,651 (of which trend_break 134; breadth anomalies 10; macro anomalies now dated by availability).
- transmissions: 5 activated (M12 mixed 0.63, M05 mixed 0.14, M09 mixed 0.14, M01 unsupported 0.05,
  M14 unsupported 0.05); p-values + BH-FDR applied per mechanism.
- opportunities: 18 = 10 watch, 6 low_priority, 2 excluded, **0 deep_research**.
  The absence of deep_research is a *result*: expectation proxies or mechanism evidence did not clear the
  explicit gates (gap≥0.15, confidence≥0.5, mechanism confidence≥0.40 + ≥2 FDR-significant tests).
- top 3 (research priority): QQQ policy-repricing (Fed hike, 0.670); SPY VIX-regime (0.662);
  XLP energy-inflation (0.653). Each carries evidence, gaps and invalidation.

## D. Historical cases (PIT slice per evaluation date)
Final: **7/7** (COVID, 2022 rate shock, UK LDI, SVB, yen carry, China policy rally, gold vs real rates).
The China case now passes through the observed-policy-action archetype (CSI 300, watch 0.678); the gold
case passes through the symmetric upside-divergence archetype (low_priority), not through a forced
mechanism narrative. Mechanisms were often `unsupported` — correctly reported, not treated as detection failure.

## E. Handoff (investment-agent)
- Run executed; downstream `run_ok=true`, evidence rows 17, but step `S8_grounded_qa` semantically failed.
- A records `semantic_status=partial`, task status `not_completed:partial`, event
  `ia_research_not_completed` — NOT success. Reason surfaced to the operator.
- Unit tests cover ok_valid / rejected / insufficient_data / partial / missing artifact / stdout `ok:false`.
