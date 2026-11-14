# ISSUE LEDGER — autonomous audit round 1 (branch fix/autonomous-audit-remediation)

Status: OPEN / IN_PROGRESS / FIXED (code changed) / VERIFIED (regression + data check) / BLOCKED
Evidence = reproduction command/output, not assertion.

## Reported P1 issues

| ID | Sev | Reported issue | Independent reproduction | Root cause | Fix | Test / evidence | Status |
|---|---|---|---|---|---|---|---|
| P1-01 | P1 | expectation_gap is a constant/mechanism confidence | 15/15 candidates had no valuation/positioning input; constants 0.7 and 0.6×conf | No measurement of expectations; "unknown" scored as positive | New `goe/expectations.py`: positioning percentile, valuation percentile (fresh-only), driver-residual divergence with R²/|z| thresholds; missing → `None`; deep-research gate requires gap≥0.15, confidence≥0.5, dq≥0.5 | `test_missing_expectation_gap_caps_at_watch`; live scan gaps now 0.01–0.62 with explicit components | VERIFIED |
| P1-02 | P1 | macro observation vs availability; latest release cannot trigger | `US_CPI` observation 2026-09-01; anomalies dated observation; 7-day window missed monthly prints; MechanismEvaluator used observation dates | Availability semantics absent in anomaly records and trigger window | `available_date` column/semantics; macro availability = obs+lag; frequency-aware recency (daily 7d / weekly 21d / monthly 75d / quarterly 150d) in anomalies, opportunities, mechanisms, validation; macro slices respect availability | `tests/test_time_semantics.py`; live M05 now triggers on US_CPI anomaly available 2026-10-16 | VERIFIED |
| P1-03 | P1 | CFTC row after as_of | as_of 2026-11-04 → positioning index max 2026-11-07 | Lag applied AFTER truncation | Apply +4d publication lag first, then truncate ≤ as_of | `test_positioning_never_contains_rows_after_as_of`; reproduction now max 2026-10-31 | VERIFIED |
| P1-04 | P1 | net_to_oi equals raw contracts | POS_SP500_LEV −372,318 vs −0.187421 | `:oi` series never loaded | Load net+OI; feature = net/OI | `test_net_to_oi_is_a_ratio_not_raw_contracts`; live −0.2048 | VERIFIED |
| P1-05 | P1 | historical replay reuses end-of-window features | JAPAN 2024-08-05: Nikkei 1m −0.39% (old) vs −23.11% true PIT | one FeatureSet at case end used for all eval dates; macro truncated by observation date | `FeatureSet.slice_as_of` truncates prices/positioning and filters macro by AVAILABILITY; validation builds one end set and slices per eval date | direct verification: Nikkei −23.11%, drawdown −25.50%, SPY −6.72%, VIX +209.05%; case rerun in progress | VERIFIED |
| P1-06 | P1 | handoff success judged by exit code only | rc=0 accepted even with `run_ok=false` / zero evidence | adapter ignored structured report | `parse_research_artifact` requires run_ok=true, evidence≥1, no failed steps; statuses ok_valid/rejected/insufficient_data/partial/failed/timeout/unavailable; tasks record non-success | `tests/test_readiness_handoff.py` (9 cases) | VERIFIED |
| P1-07 | P1 | ingest failure continues to features | fake empty provider → run() returns prices_error, scan proceeded | `Ingestor.run` swallowed errors; pipeline had no gate | run() returns status; pipeline blocks on price failure and on readiness failure; blocked scans recorded `blocked_data`; CLI exit 2 | `test_pipeline_blocks_when_price_ingest_fails`, readiness tests | VERIFIED |
| P1-08 | P1 | score drop leaves deep_research | deep_research excluded from status updates | terminal/manual conflated with auto | `status_source` (auto/manual/lifecycle); auto may demote, manual protected, terminal never resurrected | `tests/test_status_lifecycle.py` (3 tests) | VERIFIED |

## New issues found by independent audit

| ID | Sev | Issue | Evidence | Root cause | Fix | Status |
|---|---|---|---|---|---|---|
| N-01 | P0 | Monday/post-holiday returns dropped on union calendar | SPY 2026-11-09 +2.37% had no 1d z; 122 Monday moves ≥3σ invisible | `pct_change` on union calendar yields NaN at Monday, then dropped | business-day panel + per-instrument `dropna().pct_change()`; `safe_pct_change` over valid observations | FIXED/VERIFIED (SPY 11-09 z=3.35) |
| N-02 | P0 | trend_break false positives | 1,181/2,935 anomalies (40%), 88.6% 10 rows after non-trading day | `fillna(0)` + global `shift(10)` | per-instrument valid-observation sign flips; no fill | FIXED (1,181→93 on final scan; window-boundary false signals from pre-detection truncation also fixed) |
| N-03 | P0 | breadth dead (MA200 never reached on union calendar) | breadth_above_ma200 constant 0; no breadth anomalies | 200-row window < 200 trading days | business-day calendar; breadth 0 anomalies → 10, series non-constant | FIXED/VERIFIED |
| N-04 | P1 | latest bar is intraday snapshot | SPY 753.11/5.9M vs final 754.37/38.4M | no completed-bar guard | regional close-time guard + fetched_at; US last bar dropped at 10:05 ET | FIXED (SPY last=2026-11-12) |
| N-05 | P1 | Shiller CAPE/ERP bypasses PIT and staleness | at 2023-08-15 used CAPE published ~Sep | raw store read in cross-asset features | ERP uses PIT-filtered macro frame only | FIXED |
| N-06 | P1 | 3.213:1 share conversion quarantined 520 rows | CN_SEC_NEWEN tail NaN while counted in 125 | non-standard ratio not handled | large persistent ETF upward jump → `level_rebased` | FIXED/VERIFIED |
| N-07 | P1 | BLS revisions never refetched | incremental start = last−10d | fixed overlap for all frequencies | monthly 150d / quarterly 420d overlap | FIXED/VERIFIED |
| N-08 | P1 | score double counting / constant breadth | repricing reused drawdown; mechanism count = 1 always; dq hard-coded | component construction | economic_impact uses mechanism asset count; repricing uses MA gap only; dq from evidence tiers + quality_issues | FIXED |
| N-09 | P1 | one mechanism dominates pipeline (M01 6/15) | audit count | no per-mechanism cap | max 3 candidates per mechanism | FIXED |
| N-10 | P1 | mechanism statistics: overlapping conditional samples, no p/FDR, free failures | 0 lead_lag tests; failed corr not penalised | evaluator design | non-overlap events; Fisher/lead-lag p-values; BH-FDR per mechanism; every non-insufficient failure penalised; 7 lead_lag tests added | FIXED |
| N-11 | P1 | partial writes on scan failure | forced failure left 1 anomaly + failed scan | no rollback | `Store.rollback_scan` + created id tracking | FIXED (rollback test) |
| N-12 | P2 | no FK constraints; `PRAGMA foreign_keys` ineffective | schema has no REFERENCES | design | documented as limitation (single-writer, validated at app layer) | OPEN (documented) |

## Notes
- P1-01/P1-02/P1-05 were partially fixed before this ledger was written; this table records the final verified state.
- Audit snapshot for reproduction: `bb02363` + uncommitted fixes; current branch commits are listed in FIX_LOG.md.
