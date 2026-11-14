# FINAL ACCEPTANCE — round 3

Branch `fix/autonomous-audit-remediation`; base `e5da620`; prior tip `6755d34`.
Round-3 changes are committed separately (see `git log`).
Verdict: **ENGINEERING ACCEPTED / INVESTMENT RESEARCH CAPABILITY NOT YET VALIDATED**.
No P0/P1 remains after the round-3 audits and two final QA passes; P2 limitations are listed below.

## Gate 1 — Data Integrity: PASS with residuals
- Historical bar completeness is now **same-session only**: a bar fetched on a later date (backfill) is
  complete; DST-aware local closes; every bar, not just the last, is checked.
- Reproduced CSI300 2024-09-30 = **4017.855** (not 3703.685); `build(t)` vs `build(T).slice(t)` on
  real t=2025-06-30/T=2026-11-13: 5,774,728 common rows, **0 missing, 0 value mismatch** for prices,
  returns, macro, positioning and curves (split-day edge case documented below).
- Crypto uses a native 24/7 calendar, cleaned independently (weekend shocks retained; 10× bad print
  quarantined); FX exempt from equity close logic.
- Critical dependency contract: UST curve + key 2Y/10Y, US_CPI + US_POLICY_RATE are critical;
  per-market coverage; per-curve-system staleness; optional series only degrade. Readiness uses
  completed bars, so an intraday print cannot refresh a dead market.
- **Residuals**: actual CFTC/BLS/BIS publication timestamps/vintages unverified; futures roll dates
  unavailable (flagged only); split/level-rebase history is anchored on the pre-action basis;
  a future split **on the evaluation date itself** can differ between build(t) and build(T).slice(t)
  because at t the action is indistinguishable from a glitch (P2, documented).

## Gate 2 — Quantitative Correctness: PASS with residuals
- Independent recomputation matched SPY returns/vol/drawdown/z, CFTC net/OI, CPI YoY, UST changes;
  VIX 5y percentile differs by ~0.005 (row-window vs valid-observation window, known).
- P1-A bar semantics and corporate-action basis fixed; no lookahead found in the new paths.
- **Residuals**: crypto/equity window labels differ (30 natural days vs 21 bday); mechanism p-values
  are normal/Fisher approximations without HAC; same price move can still appear in anomaly + gap +
  repricing.

## Gate 3 — Engineering Reliability: PASS
- 157 offline tests pass (round-1: 97; round-2: 137); 9 network tests unchanged.
- One outer SAVEPOINT transaction around anomalies/transmissions/opportunities/events/report/export;
  forced failures leave DB empty and scan failed; files created by a failed attempt are removed.
- Detector exceptions abort and roll back; provider 1/125 success → ingest failed → scan blocked with
  `blocked_data`; report exposes ingest coverage when partial.
- Handoff: out_dir is cleared per run; report must be newer than run start; `ok_valid` requires S8
  `answered` and non-empty evidence; failed process/L2-only never recorded as completed; CLI exit 2.
- Final scan: **1,506 anomalies**, 5 mechanisms (2 mixed / 3 unsupported), **11 candidates**
  (2 watch, 3 low_priority, 2 invalidated, 4 excluded, 0 deep_research); research queue = 2.
- **Residuals (P2/P3)**: future-split evaluation-day edge case; failed-scan file cleanup covers
  reports/exports/schema; lab mode (`min_coverage=0`) disables the critical contract with a warning;
  no SQLite FK constraints.

## Gate 4 — Financial Research Methodology: PARTIAL
- Past policy prints are no longer forward catalysts; >10-day policy event candidates are demoted
  to low_priority; same-day events get 0.6 (no timestamp); 31–90 days get 0.2.
- Current candidates respect their own invalidation checks (OPP-0006 invalidated); excluded can
  re-arm; mechanism direction conflicts are removed/capped; a failed transmission can seed a
  mechanism-breakdown lead only with a conditional/lead-lag failure; one theme per candidate pool.
- Expectation gap is as-of (latest common date 11-12), self-driver excluded, local drivers added
  (DAX now uses SX5E/EUR local drivers; it no longer appears in the current candidate pool); missing data cannot reach deep.
- **Residuals**: expectation proxies are not consensus/options-implied; only the first trigger is
  checked for invalidation; policy decision dates are unavailable (BIS monthly availability only);
  evidence quality still under-weights some counter-evidence.

## Gate 5 — Opportunity Discovery: PARTIAL / NOT VALIDATED
- Strict PIT replay: **7/7** with case-entity/derived detection (no whole-market family fallback);
  mechanisms are unsupported/failed in most cases and are reported, not counted as detection.
- Current research queue: DXY event (0.593) and Nikkei BoJ event (0.558); SPY policy print is
  low_priority (0.603); DAX is no longer in the candidate pool after the local-driver correction.
- Blind round 3: engine **1.188** vs anomaly **1.521** vs price **1.312**; Precision@3 0.417 / 0.750
  / 0.500. **The engine is worse than both naive rankings in this blind sample**; round-2's small
  advantage did not replicate.
- Forward 3m (descriptive): engine +7.12% but ex-top **+2.45%**, class-relative +2.99%,
  beat-class 42%; anomaly +5.09% (ex-top +1.05%), class +5.42%, beat-class 58%. No robust edge;
  FXI contributes ~4.9pp.
- **Residual**: no human expert labels, n=12/method, candidate selection still event/mechanism-heavy;
  Gate 5 cannot be signed off as a research advantage.

## Gate 6 — Integration & Independent QA: PASS for semantic correctness; end-to-end NOT achieved
- Real handoff: downstream rc=0 but S8 `out_of_scope` → A records `refused`,
  task `not_completed:refused`, CLI exit 2; no `ok_valid` sample exists.
- Parser tests cover ok_valid/refused/rejected/insufficient/partial/timeout/missing/stale/L2-only.
- Independent QA: `R3_FINAL_QA_ENGINEERING.md` PASS WITH ISSUES, **no P0/P1**; round-3 data/research
  audits found P1s that were fixed and re-verified (`R3_DATA_AUDIT`, `R3_RESEARCH_AUDIT`,
  `R3_RED_TEAM_AUDIT`). Remaining items are P2/P3 and documented in `ISSUE_LEDGER_R3.md`.
- B's zero-model intent gate rejects asset-specific research questions; this is an external
  capability limitation (not modified).

## Independent final acceptance QA
`audit/R3_FINAL_ACCEPTANCE_QA2.md`: **PASS WITH ISSUES**, no P0/P1; P1-R1 (real refused task) and
P1-R2 (docs no false success) verified closed; remaining items are P2/P3 documentation and the
unvalidated research edge.

## Stop classification
This is **not** a full six-gate research sign-off. Engineering is accepted; investment research
capability remains unvalidated because (a) no human/expert labels, (b) no forward evidence of edge,
(c) blind round-3 favors simple anomaly ranking, (d) A→B produces no real successful deep-research
artifact. No further code change can manufacture those without new data/expert evaluation.
