# PROJECT STATE — Global Opportunity Engine

- Date: 2026-11-15
- Branch: `architecture/research-v2`
- HEAD at last state write: research-product commit (will advance with the Phase-1 scan-evidence commit)
- Main: untouched. V1: tag `v1-frozen-1f2b341`; no V1 changes.
- Current phase: **Phase 1 — Engineering Closure** (scan evidence gate), then Phase 2 research.

## Phase 1 tasks
| ID | Objective | Priority | Status | Evidence |
|---|---|---|---|---|
| P1-SCAN-1 | Release gate independently verifies real scan/data/report evidence | P0/P1 | DONE | `goe/scan_evidence.py`, `tests/test_scan_evidence.py` |
| P1-SCAN-2 | Adversarial invalid/valid scan tests | P1 | IN PROGRESS | empty, fake hash, modified content, wrong as_of, old scan, partial ingest, missing/mismatched report |
| P1-REL-1 | New proof after code freeze | P1 | DONE | `release_671f5faa5f.json`, 241 tests |
| P1-QA-1 | Independent red-team on scan evidence | P1 | DONE | QA C/D/E/F found P1s, fixed; G/H final |
| P1-QA-2 | Second independent pass / fresh clone | P1 | IN PROGRESS | QA G/H |
| P1-CI-1 | GitHub Actions cross-OS run | P1 | **SUCCESS** | run 20 0d5d6ac, 241 tests; run 19 also green |

## Phase 2 tasks (not started until Phase 1 frozen)
| ID | Objective | Status |
|---|---|---|
| P2-HYP-1 | Hypothesis-discrimination framework with distinct predictions | PARTIAL: cross-asset measured evidence + gate already implemented |
| P2-EVAL-1 | Separate selection/question/evidence/decision evaluation | PENDING: no independent human labels |
| P2-DATA-1 | Consensus / term-OIS feeds | BLOCKED: no licensed source; policy proxy only |
| P2-AB-1 | A→B lifecycle on research candidates | PENDING: current gate yields 0 research candidates |

## Current real state
- Real scan `scan-20261114T125130Z-574f7b` has 358,310 prices, 159,508 indicators, 1,506 anomalies,
  5 transmissions, 11 opportunities; report/scan-json/pipeline verified.
- V2 research gate: 20 candidates -> 0 research / 20 intelligence (`evidence_gap`) because no
  candidate has two measured discriminating hypotheses.
- DISCOVERY VALUE: **NOT VALIDATED**.
- Latest release proof: `release_671f5faa5f.json` (241 tests, scan-evidence v5).

## Next action
Freeze scan-evidence code, generate new proof, run independent QA; if PASS, mark Phase 1
ENGINEERING ACCEPTED and continue Phase 2 without reopening release-gate hardening.


## Accepted Phase-1 residuals (P2, explicit)
1. Scan evidence depends on the local 101 MB `data/goe.db` and gitignored `reports/`/`exports/`; a
   fresh clone can replay the 241-test proof but cannot re-derive scan evidence.
2. A self-consistent synthetic DB can satisfy the scan gate; there is no external signature/anchor.
3. A fabricated in-window `ingest_runs` success row can satisfy the live-ingest check.
4. Artifact-vs-DB content is not fully cross-checked; frozen artifact SHA-256 prevents post-scan file
   edits, but a DB+stats forger can stay consistent.
5. CI workflow exists but GitHub Actions has not executed; Docker Linux replay failed on Keychain.
6. No licensed consensus or term-OIS feed; OIS remains a policy-path proxy; consensus adapter only.

## Phase 2 update (after Phase 1 freeze)
- Added A→B eligibility guard: only A/B/C + `evidence_ok` can hand off; current 0 eligible, so
  `goe triage --handoff` returns 3 and retains intelligence in A.
- Added descriptive research-quality audit (`goe/research_quality.py`,
  `evaluation/RESEARCH_QUALITY_AUDIT.md`): selection/question/evidence/decision are reported
  separately; DISCOVERY VALUE remains NOT VALIDATED.
- Current: 20 intelligence / 0 research; mean measured evidence coverage 0.075.
- Data: cross-asset measured evidence active; consensus BLOCKED; OIS policy-path proxy only.
- CI: workflow present, GitHub Actions not executed; Docker Linux replay blocked by Keychain.


## P1 fix round (2026-11-15)
- P1-01: added `*.egg-info/`, `build/`, `dist/`, `*.whl` to `.gitignore`; editable install no longer
  makes the release worktree dirty. Local reproduction with Python 3.12 confirmed. GitHub Actions
  rerun is required for closure (cannot be claimed from macOS).
- P1-02: `goe/research_identity.py` derives `RC-<asof>-<instrument>-<phenomenon-hash>`; order changes
  cannot change identity. Legacy `research_v2_identity_map` preserves old→new mappings; old tasks
  remain on their original ID.
- P1-03: `goe/evidence/external.py` requires `curve_id,currency,region,curve_type,tenor,date,value,
  available_at,source`; all tenors must be the same curve/currency/region/type/date. Cross-currency,
  mixed curve, wrong type, missing tenor, different dates, stale and future data are rejected.
- Tests: 241 passed offline (before the next proof).


## P1 closure (latest)
- P1-01 GitHub Actions **SUCCESS** run 19 (`b888303`) after egg-info ignore/workflow cleanup.
- P1-02 stable content-hash IDs + identity alias table.
- P1-03 single-curve identity contract with cross-currency rejection.
- Research dimensions now separated: `research_worthiness`, `evidence_readiness`,
  `handoff_eligibility`, `research_queue`. Current: 0 research, 4 watch, 0 eligible; N225 high
  worthiness/partial evidence/retained.


## Final acceptance state (2026-11-15)
- Final code `983854f`; proof `release_983854f9a3.json` (241/241); HEAD after docs commit.
- GitHub Actions run 24 `43687214464` on `d2096b7`: **SUCCESS**; run 20 on `0d5d6ac`: **SUCCESS**; run 19 on `b888303`: **SUCCESS**.
- Independent QA: `FINAL_ENG_P1_QA.md` PASS (no P0/P1); `FINAL_RESEARCH_P1_QA.md` PASS (no P0/P1, P2 only).
- Phase 1 engineering accepted. Research: 0 research / 4 watch / 16 archive; 0 handoff eligible; N225 high-worthiness/partial-evidence/watch.
- DISCOVERY VALUE: NOT VALIDATED. A-B: no eligible candidate, no task created.


## Immutable identity + PIT round (2026-11-15)
- `upsert_research_candidate` rejects any same-id change of as_of/instruments/theme; status is
  insert-only there, so a completed candidate is never silently reopened; transitions use
  `set_research_status` (completed cannot be reopened).
- `research_theme_id` is the long-lived topic (instrument+anomaly signature, no date);
  `research_id` is the dated event id.
- External consensus/curve schemas require observation date, forecast target, publication,
  available_at, vintage, kind, source, provider, units; future publication/vintage and cross-
  currency/curve/provider/units stitching are rejected.
- Current: 20 candidates / 0 research / 4 watch / 16 archive / 0 handoff eligible; N225 high/partial/watch.


## Final PIT acceptance (2026-11-15)
- Code `360b161`, proof `release_360b1614d1.json` (241/241), HEAD `2488955`; CI run 24 `43697258390`: **SUCCESS**.
- QA: `QA_PIT_FINAL.md` PASS (no P0/P1); `QA_RESEARCH_CONFIRM.md` PASS (no P0/P1).
- PIT future vintage/observation/curve date/publication/available rejected; archived/completed cannot reopen.
- Current: 0 research / 4 watch / 16 archive / 0 eligible; N225 high/partial/watch.
- Accepted P2: OIS staleness uses available_at not curve date; archived->research_complete terminal transition; rerun log not separately archived.


## Research product stage (2026-11-15)
- CURRENT_GOAL: convert anomalies into checkable research dossiers; separate worthiness/readiness/queue/handoff.
- Built `goe/dossier.py` (18 sections), `goe/integration/capabilities.py` (B router),
  `goe/research_quality.py` (descriptive four-track audit).
- Generated real dossiers: A N225, B VIX explained, C TAIEX/QQQ/XLV evidence gap,
  D 2026-04-30 continuous-futures roll artifact. Index `research_dossiers/README.md`.
- Current: 0 research / 4 watch / 16 archive / 0 handoff eligible; DISCOVERY NOT VALIDATED.
- Stage: research workflow functional; next is independent review/evidence acquisition, not gate tuning.


## Research product validation round
- Dossiers A–D generated with 18 sections and real source refs; B relabelled "no explanatory gap"
  (not "explained"); D corrected to Cotton (CM_AGR_CT), not Live Cattle.
- Global support now requires R²>0.50 (documented H-GLOBAL threshold); VIX/QQQ are not "supported".
- 241 offline tests; proof/CI to be regenerated.


## Research execution state (2026-11-15)
CURRENT_GOAL: real research closed loop, N225.
CURRENT_RESEARCH_CASE: RC-20261113-JP_EQ_N225-455ff8e1a32f (event 2026-11-06).
CURRENT_HYPOTHESES: H-EQJP-LOCAL / GLOBAL / FX / POLICY / FUND; new H-EQJP-ASIA-REGIONAL.
EVIDENCE_ACQUIRED: PIT cross-section; prior-US 2026-11-05 SPY -4.41%, QQQ -6.49%, VIX +69.66%;
Asia same-day TOPIX -6.50%, TAIEX -4.51%, KOSPI -6.02%; USDJPY prior -0.07%.
TESTS_EXECUTED: local, global lead, Asia regional, FX, 3-day reversal; explicit thresholds.
RESEARCH_FINDINGS: `research_results/2026-11-13/N225/findings.md` and `finding.json`.
RESEARCH_UNCERTAINTY: local Japan vs regional Asia; no sector/consensus; INCONCLUSIVE; no alpha.
EVIDENCE_MISSING: TOPIX sector breadth, Asia semiconductor exposure, consensus, event-news calendar.
OPEN_BLOCKERS: B cannot deep-research Japan equity/sector; see `B_CAPABILITY_REQUEST.md`.
NEXT_ACTION: acquire sector breadth; independent QA; commit/proof/CI.
ACCEPTANCE_STATUS: research A-D functional; E pending independent QA.


## Final research closed loop (2026-11-15)
- N225 2026-11-13 / event 2026-11-06: prior-US 2026-11-05 global lead supported,
  Japan-local and North Asia co-move supported; local vs regional remains unresolved.
- Finding `research_results/2026-11-13/N225/findings.md`; status INCONCLUSIVE; DB hypotheses/finding persisted.
- Independent QA `audit/QA_RESEARCH_CLOSED_LOOP.md`: ACCEPTED (P0/P1 none).
- Code `8266fa6`, proof `release_3905c181a6.json` 241 tests, CI run 31 green.


## Generalized multi-case research (2026-11-15)
CURRENT_GOAL: generalized executor + append-only memory + orchestrator.
CURRENT_RESEARCH_CASES: N225 (equity), US_FX_DXY (FX), CM_ETF_SLV (commodity).
LATEST_COMMIT: 4fa6086 code (findings regenerated at this code).
RESEARCH_MEMORY_VERSION: append-only revisions/evidence/findings; workflow table.
RESEARCH_FINDINGS: `research_results/2026-11-13/{JP_EQ_N225,US_FX_DXY,CM_ETF_SLV}/`.
TESTS_EXECUTED: 243 offline; orchestration/memory regression included.
OPEN_BLOCKERS: B deep Japan sector attribution; consensus/OIS/CFTC/inventory unavailable.
NEXT_ACTION: independent QA, proof, CI, B request delivery.
ACCEPTANCE_STATUS: multi-case functional; research value NOT VALIDATED.
