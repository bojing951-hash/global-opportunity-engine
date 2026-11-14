# FINAL ACCEPTANCE — autonomous audit round 1

Branch `fix/autonomous-audit-remediation`; base `e5da620`; audit baseline `bb02363`.
Verdict: **PASS WITH ISSUES** (all reported P1s fixed and independently re-verified; several
newly-found P0/P1s fixed; residual limitations explicit, no fabricated validation).

## 1. Engineering correctness
- 121 offline tests pass (was 97); 9 network tests unchanged; full suite 130 collected.
- No partial writes: forced scan failure rolls back anomalies/transmissions/created opportunities
  (`test_failed_scan_rolls_back_partial_records`).
- Readiness gate blocks failed ingest/stale coverage and records `blocked_data`; readiness is
  disclosed in scan meta/report.
- CLI status supports `--auto` to release a manual hold.
- **Residual**: no SQLite FK constraints (single-writer, validated at app layer); one mechanism can
  still be `mixed` with very low confidence (0.05) — reported, not hidden.

## 2. Data reliability
- Provenance complete (0 null source_id/fetched_at in 358,310 prices / 159,508 indicators).
- Fixed: CFTC lookahead (as_of 2026-11-04 max row 2026-10-31) and net/OI (−0.2048 ratio);
  Monday/post-holiday returns (SPY 2026-11-09 z=3.35); dead breadth; 40%→5.6% trend_break artefacts;
  intraday last bar dropped (US last = 2026-11-12); ERP PIT; 3.213:1 conversion rebased;
  BLS/BIS revision lookback (monthly 150d).
- **Residual/unverifiable**: actual CFTC/BLS publication timestamps vs assumed lags; futures roll
  contamination (no contract metadata); vendor revision magnitude; A-share proxy quality.

## 3. Research-method reliability
- Expectation gap is now measured (positioning/valuation/residual) with explicit `None`; no
  constant 0.7 / 0.6×confidence remains. Missing expectation cannot reach `deep_research`.
- Score double counting removed; data quality from evidence tiers/provider issues; mechanism
  dominance capped at 3.
- Mechanism tests: non-overlapping conditional samples, Fisher/lead-lag p-values, BH-FDR,
  every failure penalised; 7 lead-lag tests added.
- **Residual**: expectation proxies are not consensus/options-implied data; regression cannot
  establish causality; the sample of tests is still small; no out-of-sample forward test.

## 4. Real screening ability
- Historical replay with independent PIT slices: **7/7** (COVID, 2022 rate shock, UK LDI, SVB,
  yen carry, China policy rally, gold vs real rates).
- Current scan: 1,649 anomalies, 5 mechanisms (2 mixed/3 unsupported), 18 candidates
  (9 watch, 7 low_priority, 2 excluded, **0 deep_research**).
- Top-3 research objects: QQQ policy repricing (Fed hike, 0.670), SPY VIX regime (0.662),
  XLP energy-inflation chain (0.653); each has a measurable gap or explicit gap=None and
  evidence/invalidations.
- Blind benchmark (4 dates, 36 objects): engine mean 1.29 vs anomaly-score 1.27 vs price-move
  1.17; Precision@3 0.50 vs 0.25 vs 0.00; **counterexample 2025-06-30 engine 0.67 vs 1.50**.
- **Residual**: no forward-return or human-expert validation; 0 deep_research today is the honest
  result of the stricter gates, not a claim that nothing is investable.

## 5. Research handoff
- Real run: downstream `run_ok=true`, 17 evidence rows, but `S8_grounded_qa` semantically failed →
  A records `partial` / `not_completed:partial`, not success; event `ia_research_not_completed`.
- Parser unit tests cover ok_valid / rejected / insufficient_data / partial / missing artifact /
  stdout `ok:false`; `investment-agent` was not modified.

## 6. Reproducibility
```bash
.venv/bin/python -m pytest tests -m "not network" -q
.venv/bin/python -m goe.cli scan --no-ingest
.venv/bin/python -m goe.cli replay --cases
.venv/bin/python -m goe.cli handoff --ia-path ~/investment-agent-dev --limit 1
```
Artifacts: `audit/ISSUE_LEDGER.md`, `FIX_LOG.md`, `VALIDATION_RESULTS.md`, `RESEARCH_QUALITY.md`,
`reports/report_2026-11-13.md`, `reports/validation_cases_*.md`.

QA: independent reviewer verdict **PASS WITH ISSUES**, no original P1 unresolved
(`audit/FINAL_QA_AUDIT.md`). Responses to its residual risks are in `audit/QA_RESPONSE.md`;
the only acknowledged unfixed items are the absence of forward-return/human validation, approximate
mechanism p-values without HAC, and non-atomic mid-`persist_drafts` failure (disclosed, not claimed).
