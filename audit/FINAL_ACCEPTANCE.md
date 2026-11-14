# FINAL ACCEPTANCE — recursive audit round 2 (current worktree)

Branch `fix/autonomous-audit-remediation`; base `e5da620`; round-1 tip `7c5df4c`;
round-2 changes are committed separately (see `git log`).

**Overall verdict: ENGINEERING ACCEPTED / INVESTMENT RESEARCH CAPABILITY NOT YET VALIDATED.**
No P0 and no unaddressed P1 after the two independent audits and two QA rounds;
research edge and human/expert validation remain unproven (Gate C/D PARTIAL).

## A. Engineering — PASS
- 137 offline tests pass (round-1: 97); 9 network tests unchanged.
- One SQLite transaction (savepoint-aware) around anomalies, transmissions, opportunities,
  status events, reports, export and scan finish; forced `write_reports` failure and detector
  failure both leave **0 anomalies/0 opportunities/0 events**, scan `failed`/`rolled_back`.
- Detector exceptions abort the scan instead of silently dropping a signal family.
- `run_scan` without `--as-of` now applies wall-clock staleness (scan is blocked, `blocked_data`).
- Handoff CLI returns exit 2 when downstream is not `ok_valid`.

## B. Data reliability — PASS with documented residuals
- Provenance complete; independent recomputation matched SPY return/vol/drawdown/z,
  CFTC net/OI (−0.2048), CPI YoY (3.7377 for 2026-09), UST changes within rounding.
- Fixed: CFTC lookahead and net/OI; missing-OI fallback to raw net; Monday returns; dead breadth;
  trend_break false crosses (1,181→~93/scan); intraday bar; PIT ERP; 3.213:1 share conversion;
  revision lookback; macro availability; frequency-aware recency.
- Readiness: per-market configured/tracked/fresh coverage (dead UK/CN critical), latest
  AVAILABLE macro (unpublished print is not falsely stale), per-curve-system stale critical,
  wall-clock for implicit latest. Final scan: `degraded=True` (EA_HICP 347d stale) but
  `critical_degraded=False`, so a single stale optional series does not globally disable deep research.
- **Residual/unverifiable**: actual CFTC/BLS/BIS publication timestamps and vintages; futures
  contract-level roll dates (only flagged, not adjusted); FX/local-currency returns not converted
  to USD; vendor revision magnitude; A-share proxy quality.

## C. Research methodology — PARTIAL
- Expectation gap is measured (positioning / fresh valuation / 1m driver residual) with explicit
  `None`; current residual row is the latest common date (11-12), not a 21-day sampling phase;
  self-driver removed; local market/FX drivers added; missing OI makes the ratio unknown.
- Past events no longer score as forward catalysts; current candidates respect their own
  `invalidation_checks`; mechanism `expected_direction` contradictions are removed or capped;
  evidence quality includes counter-evidence and mechanism confidence; one theme per candidate.
- Mechanism tests: non-overlapping conditional samples, Fisher/lead-lag p-values with lag-search
  correction, BH-FDR per mechanism, all failures penalised.
- **Residual**: expectation proxies are not consensus/options-implied data; regression cannot
  establish causality; the same price move can still influence anomaly/gap/repricing
  (not fully orthogonal); mechanism p-values are normal approximations without HAC.

## D. Opportunity discovery — PARTIAL (discovery demonstrated; edge not proven)
- Strict point-in-time replay: **7/7**, now using **case-entity** detectors (plus derived series such
  as CREDIT_RISK from HYG/IEF), not the whole-market detector set. Two misses found by the stricter
  rule were addressed by a general **mechanism-breakdown** archetype (gold vs real yields) and the
  derived-series mapping (SVB credit stress), not by case-specific hardcoding.
- Current scan: **1,511 anomalies**, 5 mechanisms (2 mixed / 3 unsupported), **11 candidates**
  (3 watch, 2 low_priority, 1 invalidated, 5 excluded, 0 deep_research). Research queue: 5
  (watch+low); invalidated/excluded not handed off.
- Top-3 research objects: SPY policy repricing (0.606), DXY event revision (0.593),
  Nikkei policy repricing (0.548); no duplicate primary assets. The top candidate's catalyst is a
  28-day-old policy print (score 0.10, not 1.0), so it is not a claim of a fresh event.
- Blind round 2 (globally shuffled IDs): engine mean 1.250 vs anomaly 1.229 vs price 1.062;
  Precision@3 0.417 / 0.333 / 0.083; **counterexample 2025-06-30 engine 0.75 vs anomaly 1.17**.
  Fact cards are not equal-information: engine picks more mechanism-tagged objects, so the rater
  can reward mechanism presence; effect size is +0.021 over anomaly ranking.
- Forward 3m (descriptive): engine +7.12% (excess SPY +0.56%, class-relative +2.99%,
  beat-class 42%) vs anomaly +5.09% (class +5.42%, beat-class 58%). Higher mean, lower hit rate;
  no robust edge and no return claim.
- **Residual**: no human expert labels; n=12/method; research value ≠ directional return.

## E. A→B handoff — PASS for semantic correctness; end-to-end not achieved
- Real run: downstream process rc=0 but S8 returns `out_of_scope`; A records
  `semantic_status=refused`, task `not_completed:refused`, event `ia_research_not_completed`,
  CLI exit 2. It does NOT claim success.
- Parser now requires S8 `answered` for `ok_valid`, distinguishes `refused`, `partial`,
  `insufficient_data`, `rejected`; unit tests cover each branch.
- **Not achieved**: a real `ok_valid` deep-research handoff. B's zero-model intent gate rejects the
  asset-specific question even when worded as non-advice; modifying B is outside this task.
  This is recorded as an external capability limitation, not an A success.

## Independent QA
- Round-1: `audit/FINAL_QA_AUDIT.md` — PASS WITH ISSUES, no original P1 unresolved.
- Round-2: `audit/ROUND2_DATA_AUDIT.md`, `audit/ROUND2_RESEARCH_AUDIT.md`,
  `audit/FINAL_QA_ROUND2.md` — PASS WITH ISSUES. The two round-2 P1s it found were fixed:
  (1) a single stale series globally capping deep research → split `degraded` vs
  `critical_degraded`; (2) all UST tenors stale not critical → per-curve-system critical check.
  Remaining items are P2 and documented in `audit/ROUND2_FIX_SUMMARY.md`.

## Reproduction
```bash
.venv/bin/python -m pytest tests -m "not network" -q
.venv/bin/python -m goe.cli scan --no-ingest
.venv/bin/python -m goe.cli replay --cases
.venv/bin/python -m goe.handoff ...   # via CLI: goe handoff --ia-path ~/investment-agent-dev --limit 1
```
Artifacts: `reports/report_2026-11-13.md`, `reports/validation_cases_20261114T063037Z.md`,
`audit/VALIDATION_RESULTS.md`, `audit/RESEARCH_QUALITY.md`, `audit/FORWARD_RETURNS.md`.
