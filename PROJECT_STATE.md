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
| P1-REL-1 | New proof after code freeze | P1 | DONE | `release_671f5faa5f.json`, 235 tests |
| P1-QA-1 | Independent red-team on scan evidence | P1 | DONE | QA C/D/E/F found P1s, fixed; G/H final |
| P1-QA-2 | Second independent pass / fresh clone | P1 | IN PROGRESS | QA G/H |
| P1-CI-1 | GitHub Actions cross-OS run | P1 | **SUCCESS** | run 20 0d5d6ac, 235 tests; run 19 also green |

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
- Latest release proof: `release_671f5faa5f.json` (235 tests, scan-evidence v5).

## Next action
Freeze scan-evidence code, generate new proof, run independent QA; if PASS, mark Phase 1
ENGINEERING ACCEPTED and continue Phase 2 without reopening release-gate hardening.


## Accepted Phase-1 residuals (P2, explicit)
1. Scan evidence depends on the local 101 MB `data/goe.db` and gitignored `reports/`/`exports/`; a
   fresh clone can replay the 235-test proof but cannot re-derive scan evidence.
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
- Tests: 235 passed offline (before the next proof).


## P1 closure (latest)
- P1-01 GitHub Actions **SUCCESS** run 19 (`b888303`) after egg-info ignore/workflow cleanup.
- P1-02 stable content-hash IDs + identity alias table.
- P1-03 single-curve identity contract with cross-currency rejection.
- Research dimensions now separated: `research_worthiness`, `evidence_readiness`,
  `handoff_eligibility`, `research_queue`. Current: 0 research, 4 watch, 0 eligible; N225 high
  worthiness/partial evidence/retained.


## Final acceptance state (2026-11-15)
- Final code `983854f`; proof `release_983854f9a3.json` (235/235); HEAD after docs commit.
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
- Code `360b161`, proof `release_360b1614d1.json` (235/235), HEAD `2488955`; CI run 24 `43697258390`: **SUCCESS**.
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
- 235 offline tests; proof/CI to be regenerated.
