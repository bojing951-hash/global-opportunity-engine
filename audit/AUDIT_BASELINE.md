# AUDIT BASELINE — 2026-11-14 09:40 HKT

## Repository
- Repo: https://github.com/bojing951-hash/global-opportunity-engine (public since 2026-11-14 08:40 HKT)
- Branch before audit: `main` @ `e5da620cafce5b6214252de35538c70f7112aa3a`
- Audit branch: `fix/autonomous-audit-remediation`
- External audit commit: `e5da620` (same as current main; no upstream drift at start)
- Worktree: clean at start

## Environment
- macOS 15.6.1 arm64; Python 3.12.13 (uv venv); SQLite `data/goe.db`
- investment-agent checkout: `~/investment-agent-dev` @ `bdf5b9e` (read-only for this audit)

## Measured baseline (own run, not copied from prior audit)
| Item | Value | Command |
|---|---|---|
| Instruments with prices | 125 / 125 configured | SQL distinct instrument_id |
| Price rows | 358,310 | SQL count |
| Indicator rows / series | 159,508 / 92 | SQL count |
| CFTC OI rows stored | 9,888 (`:oi`) | SQL count |
| Anomalies (last scan) | 2,935 | SQL count |
| Transmissions | 8 (6 mixed, 1 weak, 1 unsupported) | SQL group by |
| Opportunities | 15 (2 deep_research, 11 watch, 2 low_priority) | SQL group by |
| Offline tests | 97 passed | `pytest tests -m "not network"` |
| Network tests | 9 passed | `pytest tests -m network` |
| Historical cases | 7 / 7 (stored artifact) | `reports/validation_cases_*.md` |

Discrepancy note: the external audit reported 358,280 prices / 159,522 indicators / 2,794 anomalies /
10 transmissions / 14 opportunities. Those numbers differ from this baseline (different run time and
post-cleanup DB). This audit re-derives every number from the current checkout and database.

## Time semantics baseline (to be fixed)
- `prices.date` = trading date of the observation.
- `indicators.date` = observation date (reference period), `fetched_at` = UTC ingestion time.
- `_load_macro` filters by `observation_date + release_lag <= as_of` but keeps the observation date as the
  feature index → macro anomalies are dated in the past and can miss short recent-window screening.
- `_load_positioning` truncates at `as_of` FIRST and adds a 4-day publication lag SECOND → rows dated after
  `as_of` can appear (P1-03) and OI columns are not loaded at all (P1-04).
