# QA RESPONSE — actions taken on FINAL_QA_AUDIT findings

Independent QA verdict: **PASS WITH ISSUES**; no original P1 unresolved. Below is the response
to its five residual risks. Some doc numbers in the QA report refer to the scan before the last
two fixes (1,659) — final scan after fixes is 1,649 and all documents are aligned to it.

## 1. N-02 trend_break boundary artefacts (P1) — FIXED
Root cause: `detect_anomalies(since=...)` truncated `fs.long` **before** running detectors, so
windowed detectors saw only the window; `shift(10)` then referenced missing history and produced
false flips at the window start (QA: 45/134 within 2026-04-27..05-14).

Fix (`goe/anomalies.py`): detectors now always run on the full history; only the **emitted**
anomalies are filtered to `since` (before flood control). Result on final scan: 93 trend_break
(5.6% of 1,649), no boundary-only cluster. Historical replay re-run after this fix (see
`reports/validation_cases_*.md`).

## 2. Mechanism statistics optimism (P2) — PARTIALLY FIXED
- effective n no longer floored at 10; floor is 4 (`max(4, len/window)`), so 1636/250=6.5 is
  reported as 6.5 rather than 10.
- lead-lag p-value now Bonferroni-corrected for the 2·max_lag+1 lag search.
- Effect: M12 confidence 0.63 → 0.55; M09 moved mixed → unsupported on the final scan.
- **Residual:** these are still approximate (Fisher normal approximation, no HAC); mechanism
  confidence remains descriptive, not causal. Documented in LIMITATIONS.

## 3. Docs vs DB numbers (P2) — FIXED
Final scan: **1,649 anomalies**, 5 mechanisms (2 mixed / 3 unsupported), 18 candidates
(9 watch / 7 low_priority / 2 excluded / 0 deep_research). Updated:
`TEST_RESULTS.md`, `audit/VALIDATION_RESULTS.md`, `audit/FINAL_ACCEPTANCE.md`, `README.md`,
`PROJECT_SPEC.md`, `docs/DATA_SOURCES.md` (125 instruments), `docs/SCORING.md`
(residual min observations = 36, not ≥38).

## 4. Screening ability only LLM-blind (P2) — ACKNOWLEDGED, NOT PATCHED
- No forward-return or human-expert validation exists; `audit/RESEARCH_QUALITY.md` states the
  benchmark is modest (engine mean 1.29 / P@3 0.50 vs anomaly 1.27 / 0.25 vs price 1.17 / 0.00)
  and keeps the 2025-06-30 counterexample (engine 0.67 vs anomaly 1.50).
- Gate 4 is therefore **PARTIAL** in FINAL_ACCEPTANCE, not PASS. No metric is fabricated.

## 5. Rollback/handoff signals (P2)
- `goe handoff` now returns exit code 2 when any run is not `ok_valid`; the task table and event
  log already recorded `partial` / `not_completed:partial`.
- **Residual:** rollback covers scan-stage failure via `Store.rollback_scan`, but a failure in the
  middle of `persist_drafts` is not a single transaction and could leave some created/updated
  opportunities and status events. This is disclosed rather than claimed atomic. A future fix is
  a single SQLite transaction around persist + finish.
- No real `ok_valid` handoff was observed (downstream S8 fails); parser unit tests cover the
  semantic branches. Not claimed as a real success case.
