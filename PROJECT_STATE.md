# PROJECT STATE — Global Opportunity Engine

- Date: 2026-11-15
- Branch: `architecture/research-v2`
- HEAD at last state write: Phase-1 freeze commit (will advance with the Phase-1 scan-evidence commit)
- Main: untouched. V1: tag `v1-frozen-1f2b341`; no V1 changes.
- Current phase: **Phase 1 — Engineering Closure** (scan evidence gate), then Phase 2 research.

## Phase 1 tasks
| ID | Objective | Priority | Status | Evidence |
|---|---|---|---|---|
| P1-SCAN-1 | Release gate independently verifies real scan/data/report evidence | P0/P1 | IN PROGRESS | `goe/scan_evidence.py`, `tests/test_scan_evidence.py` |
| P1-SCAN-2 | Adversarial invalid/valid scan tests | P1 | IN PROGRESS | empty, fake hash, modified content, wrong as_of, old scan, partial ingest, missing/mismatched report |
| P1-REL-1 | New proof after code freeze | P1 | DONE | `release_9d51769823.json`, 219 tests |
| P1-QA-1 | Independent red-team on scan evidence | P1 | DONE | QA C/D/E/F found P1s, fixed; G/H final |
| P1-QA-2 | Second independent pass / fresh clone | P1 | IN PROGRESS | QA G/H |
| P1-CI-1 | GitHub Actions cross-OS run | P1 | BLOCKED | workflow exists; Docker Keychain blocked; no GitHub runner |

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
- Latest release proof: `release_9d51769823.json` (219 tests, scan-evidence v5).

## Next action
Freeze scan-evidence code, generate new proof, run independent QA; if PASS, mark Phase 1
ENGINEERING ACCEPTED and continue Phase 2 without reopening release-gate hardening.


## Accepted Phase-1 residuals (P2, explicit)
1. Scan evidence depends on the local 101 MB `data/goe.db` and gitignored `reports/`/`exports/`; a
   fresh clone can replay the 219-test proof but cannot re-derive scan evidence.
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
