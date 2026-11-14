# FIX LOG — round 1

Base: `e5da620` (main) → branch `fix/autonomous-audit-remediation`.
Commits are created in themed batches; see `git log --oneline main..HEAD`.

## Batch 1 — data correctness (P0/P1)
| Change | Files | Why |
|---|---|---|
| CFTC publication lag applied before truncation; `:oi` loaded; net/OI = ratio | `goe/features.py` | P1-03 lookahead, P1-04 wrong normalisation |
| Business-day feature panel; per-instrument returns on valid observations; `safe_pct_change` over valid observations | `goe/features.py` | Monday/post-holiday returns were dropped; MA200 never reached (dead breadth); window semantics counted weekends |
| Completed-bar guard by regional close + `fetched_at` | `goe/features.py` | Latest bar was an intraday snapshot |
| Shiller CAPE/ERP only via PIT-filtered macro frame | `goe/features.py` | ERP bypassed release lag/staleness |
| `trend_break` evaluated on each instrument's valid observations (no global fillna/shift) | `goe/anomalies.py` | 40% of anomalies were fake crosses 10 global rows after closures |
| Large persistent ETF upward jumps rebased (non-standard share conversion) | `goe/features.py` | CN_SEC_NEWEN 3.213:1 had 520 rows quarantined |
| Revision-aware incremental lookback (monthly 150d / quarterly 420d) | `goe/ingest.py` | BLS/BIS revisions were never re-fetched |

## Batch 2 — time semantics & replay (P1-02/P1-05)
| Change | Files | Why |
|---|---|---|
| `available_date` on anomalies + DB migration; macro availability = obs + lag | `goe/anomalies.py`, `goe/db.py`, `goe/pipeline.py` | Anomalies were dated by observation; monthly release could never enter recent-window screening |
| Frequency-aware recency (daily 7 / weekly 21 / monthly 75 / quarterly 150) | `goe/timesemantics.py`, `goe/opportunities.py`, `goe/transmission/evaluator.py` | 7-day window for monthly data was contradictory by construction |
| `FeatureSet.slice_as_of`: prices/positioning truncated, macro filtered by availability | `goe/features.py`, `goe/validation.py` | Replay reused end-of-window features; macro prints leaked into earlier evaluation dates |

## Batch 3 — research methodology (P1-01, ranking)
| Change | Files | Why |
|---|---|---|
| Measured expectation gap: positioning percentile, valuation percentile (fresh only), driver-residual divergence (R²/z thresholds), explicit `None` | `goe/expectations.py`; `goe/opportunities.py`; `config/scoring.yaml`; `docs/SCORING.md` | Constants/mechanism confidence are not expectations; "unknown" was rewarded |
| Deep-research gates: gap≥0.15, confidence≥0.5, dq≥0.5, no critical gap; regime also requires mechanism confidence≥0.40 + ≥2 FDR-significant tests | `goe/opportunities.py` | Prevent unmeasured expectations from becoming top research tasks |
| Score de-duplication: breadth = mechanism asset count; repricing uses MA gap only; dq from evidence tiers + quality issues | `goe/opportunities.py`, `goe/anomalies.py` | Same anomaly/drawdown/mechanism counted in multiple components; hard-coded dq |
| Per-mechanism cap 3 | `goe/opportunities.py` | M01 produced 6/15 candidates |
| Mechanism statistics: non-overlapping conditions, Fisher/lead-lag p-values, BH-FDR per mechanism, all failures penalised, 7 lead-lag tests added | `goe/transmission/evaluator.py`, `config/mechanisms.yaml` | No multiplicity control; failed weak correlations were free; no lead-lag coverage |

## Batch 4 — engineering (P1-06/07/08)
| Change | Files | Why |
|---|---|---|
| Downstream semantics parser (run_ok / evidence rows / failed steps) and explicit statuses | `goe/integration/ia_adapter.py` | rc=0 was treated as research success |
| Readiness gate + ingest failure blocks scan; blocked scans recorded; CLI exit 2 | `goe/readiness.py`, `goe/pipeline.py`, `goe/cli.py` | Stale data could still produce "fresh" opportunities |
| `status_source` auto/manual/lifecycle; auto may demote; manual protected; terminal not resurrected | `goe/db.py`, `goe/opportunities.py`, `goe/cli.py` | deep_research was never downgraded |
| Scan rollback on failure (anomalies/transmissions/created opportunities) | `goe/db.py`, `goe/pipeline.py` | Partial writes on errors |

## Tests added
- `tests/test_time_semantics.py` (3): observation vs availability, recency, slice.
- `tests/test_data_integrity.py` (+7): Monday returns, split vs glitch, ratio, revisions, incomplete bar, breadth, rebase.
- `tests/test_readiness_handoff.py` (9): readiness gate, downstream semantics.
- `tests/test_status_lifecycle.py` (3): downgrade, manual protection, terminal.
- `tests/test_pipeline_e2e.py` (+1): rollback.
- `tests/test_scoring.py` (+1): missing gap caps at watch.
Offline suite: 121 passed (from 97).
