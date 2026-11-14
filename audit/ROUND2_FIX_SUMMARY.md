# ROUND 2 — independent audit findings → fixes → verification

Two independent subagents audited HEAD `7c5df4c` plus the then-uncommitted worktree:
`ROUND2_DATA_AUDIT.md` (A/B) and `ROUND2_RESEARCH_AUDIT.md` (C/E). They found new
P1s; this is what was changed and how it was checked.

## Data / engineering findings
| Finding | Fix | Verification |
|---|---|---|
| Macro freshness falsely called unpublished latest print "stale" (audit: fresh 5/16; historical 0/16) | select latest observation with `obs+lag<=target`; pending prints neither fresh nor stale | fresh 14/16 on 2026-11-13; historical 15/16; readiness tests |
| Dead small markets hidden by global coverage (UK/CA/etc. disappeared) | per-region configured/tracked/fresh coverage; missing region critical when configured>=3 and min_coverage>0; 10-day holiday tolerance | new missing-UK and CN-outage tests |
| Detector exceptions swallowed; scan "success" with missing family | pipeline checks `anomalies.attrs["errors"]` and aborts transaction | fault-injection test; detector error → rollback |
| `run_scan(as_of=None)` bypassed wall-clock staleness | pass `as_of_arg` (None) to readiness so implicit-latest wall-clock applies | test implicit-latest blocked |
| Failed scan could leave DB half-written | SAVEPOINT-aware `Store.transaction`; one outer transaction around persistence+reports+export | report-failure test now also asserts zero events; nested rollback test |
| Missing OI silently fell back to raw net contracts | missing OI → `net_to_oi` unknown (never raw net) | new P1-04 regression test |
| Conditional test added publication lag twice | macro features already availability-dated; lag=0 | test updated |
| Continuous futures roll gap | every futures candidate flagged, dq×0.9, gap disclosed (`近月换月` flag); no false precision | OPP-0012/13 show roll_risk + gap |

## Research methodology findings
| Finding | Fix | Verification |
|---|---|---|
| Past events scored as ≤10-day catalysts (QQQ #1) | catalyst only for `0<=days<=10` / `<=30`; past → 0.1 | past-catalyst test; QQQ 0.670→0.606 (and no longer #1) |
| Current candidate ignored its own invalidation checks (VIX3M already back in [-1,1]) | evaluate `_checks_breached` for current fingerprints too; status invalidated | current-invalidation test; live scan OPP-0006 invalidated |
| Mechanism expected_direction never read (XLP expected down, +5.8%) | low-confidence contradictions skipped; high-confidence flagged + deep cap | XLP removed; direction-conflict gate |
| Residual gap "current" stuck on 2026-10-30 | current = latest common valid row; lag>10d unavailable; record lag/n_obs/history_start | QQQ/XLP/EEM gaps recomputed as-of 11-12 |
| SPY used as its own market driver (R²=1, zero residual) | skip self; local index fallback; local FX drivers for JP/EA/UK/CH/AU/KR/BR/MX | SPY gap now from dollar/rates; evidence shows drivers |
| One asset/theme ranked multiple times | final cap: one object per theme across archetypes; themes on policy/event drafts | scan has zero duplicate primaries |
| Evidence quality ignored mechanism strength/counter-evidence | 0.45 tier +0.25 independence +0.15 mechanism +0.15 counter-evidence; breadth confidence-scaled | config/docs/code aligned |
| 7/7 validation used whole-market detector set | case-entity detectors (plus derived CREDIT_RISK from HYG/IEF etc.); mechanism mixed needs conf≥0.30 | final strict replay 7/7 with entity-specific hits; SVB only via derived credit |
| A→B refusal reported as "partial" | parser reads S8 envelope status; out_of_scope → `refused`; ok_valid requires S8 answered; L1/L2 counts | real handoff `refused`, exit 2; parser tests |
| Blind eval IDs grouped by method; duplicate entities | global shuffle before ID assignment; class-relative forward benchmark | regenerated input/mapping/ratings; forward report updated |
| Mechanism failure itself is a research lead | new `mechanism_breakdown` archetype (failed tests n≥100, one primary asset, cap 2, status≤watch) | gold 2025 case now surfaces "gold vs real yields relationship failed" |

## Final state (this round)
- Offline tests: 135 passed.
- Scan: 1,511 anomalies; 5 mechanisms (2 mixed / 3 unsupported); 11 candidates
  (3 watch, 2 low_priority, 1 invalidated, 5 excluded), zero duplicate primaries, 0 deep_research.
- Strict PIT replay: 7/7 (case-entity detection; derived proxies counted).
- Blind round 2: engine 1.250 vs anomaly 1.229 vs price 1.062; Precision@3 0.417/0.333/0.083;
  2025-06-30 counterexample (0.75 vs 1.17) retained.
- Forward 3m: engine +7.12% (excess SPY +0.56%, class +2.99%, beat-class 42%) vs anomaly
  +5.09% (class +5.42%, beat-class 58%) — higher mean, lower hit rate; no robust edge.
- Handoff: real run refused by downstream (`out_of_scope`); A records `refused` /
  `not_completed:refused`, exit 2. No `ok_valid` real sample.

## Remaining (documented, not hidden)
- No human/expert labels; single LLM rater; forward sample n=12/method and mixed assets.
- Mechanism p-values are normal/Fisher approximations, no HAC; lag-search correction is conservative.
- Same price move can still be reflected in anomaly + gap + repricing (not fully orthogonalized);
  documented as a ranking limitation.
- Futures roll dates cannot be identified without contract metadata; only flagged.
- FX/local-currency returns are not converted to USD in the feature layer; disclosed as a limitation.
- Mid-`persist_drafts` failure now covered by the outer transaction, but report/export files written
  before a later failure may remain on disk (DB is rolled back).
