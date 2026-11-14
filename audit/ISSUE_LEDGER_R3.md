# ROUND 3 — independent audit findings and resolution

Snapshot: HEAD `6755d34` + round-3 uncommitted work. Three independent auditors:
`R3_DATA_AUDIT.md`, `R3_RESEARCH_AUDIT.md`, `R3_RED_TEAM_AUDIT.md`.

## P1 / release-blocking

| ID | Finding | Fix | Verification | Status |
|---|---|---|---|---|
| P1-A | Historical bar completeness compared a later backfill's clock hour to the bar-date close; CSI300 2024-09-30 used 3703.685 instead of 4017.855 and build(t)≠build(T).slice(t) | `bar_is_complete`: same-session only; later fetch = complete; DST-aware local close via zoneinfo; evaluate EVERY bar, not only last; split/conversion adjustment anchors pre-split history and adjusts post-split | real CSI300=4017.855; real build(t) vs T slice exact (0 missing/0 mismatch); synthetic split/future-action property; US summer/winter DST tests | FIXED |
| P1-B | Deleting core macro/UST did not always block; partial curve missing silent; readiness could be bypassed by an intraday bar; provider 1/125 success still scan success | Critical dependency contract: required macro (US_CPI, US_POLICY_RATE), required curve (UST) and key tenors (2Y,10Y); per-market and per-curve-system checks; `critical_degraded` separate from disclosure; readiness uses completed bars; ingest coverage (n_failed/targets) classifies partial/failed; ingest meta exposed | adversarial matrices; tests for key tenor, partial bar, partial provider; real readiness ok/degraded/critical=False | FIXED |
| P1-1 | A→B recorded rc=17/L2-only/stale artifact as completed; CLI exit 0 | clear out_dir before run; parser requires S8 answered + non-empty evidence_index + report mtime after run start; persist uses `status=="ok"` not semantic alone; CLI exits 2 if status != ok | fake IA matrix + tests; real refusal task `not_completed:refused`, exit 2 | FIXED |
| P1-2 | Price provider updating 1/125 targets still `success`, report claimed 100% coverage | `IngestStats.n_failed`, coverage-based status: <50% failed; provider crashes caught; pipeline records blocked_data; meta["ingest"] included in report | unit test 1/125 → failed; scan blocks; report ingest disclosure path | FIXED |
| P1-3 | Readiness raw-row freshness could be reset by one same-session partial bar | readiness computes last COMPLETE bar per instrument using the same DST-aware helper; global/region age and coverage use completed data | synthetic 10-day-old + partial bar → last_price 2024-12-31, age 10, blocked | FIXED |
| P2-1 | Crypto native features bypassed `clean_price_panel`; 10× bad print produced +900% return/anomalies | clean crypto on native calendar before features; dedupe issues; same-day crypto bar rejected; FX completeness exempt | bad crypto test return<1, quarantine present; weekend test still passes | FIXED |
| P2-2 | `slice_as_of` lost macro series that became stale at T | stale macro series keep history; staleness is metadata, current use refused | real t=2025-06-30 vs T=2026-11-13: 5,774,728 common rows, 0 missing, 0 mismatch | FIXED |
| P2-3 | config hash omitted themes/sources/cases; data hash only row counts | include all config files; content hash of prices/indicators | data revision changes hash test | FIXED |
| P2-4 | Failed scan left report/export files | remove files created by the attempt (mtime >= start) on exception | fault test: leaked report removed | FIXED |
| P2-5 | Docs test counts inconsistent (121/137/93) | updated to final offline count | see TEST_RESULTS/FINAL_ACCEPTANCE | FIXED |
| P3 | provider exception traceback, empty-frame no scan row, future as_of clamp, lab mode warning, crypto window labels | caught exceptions; blocked scan row; explicit warning; labels/limitations | tests/manual | PARTIAL/DOCUMENTED |

## Research-quality findings (R3_RESEARCH_AUDIT)
- Policy-event candidates used BIS availability date as a forward catalyst; now no catalysts field, age disclosure, >10-day candidates capped low_priority (top-1 SPY policy demoted).
- `excluded` was terminal; now auto-rearm allowed and tested.
- Catalyst 31–90 days now 0.2 per docs; same-day = 0.6 (no timestamp).
- Validation pass now requires expected detectors (not broad family), derived proxies require all parents.
- Mechanism-breakdown requires a non-correlation (conditional/lead-lag) failure, not just weak unconditional correlation.
- Remaining P2/P3: only first trigger checked for invalidation; event/mechanism breakdown lack automatic checks; policy decision date unknown (BIS monthly availability); top-10 still includes archived/excluded records in the report (separate section); blind evaluation fact asymmetry and FXI outlier documented.
