# FINAL ACCEPTANCE — current branch state

- Date: 2026-11-15
- Branch: `architecture/research-v2`
- Engineering baseline: code `671f5fa` + Phase-2 proof `release_671f5faa5f.json` (230 tests)
- Phase-2 additions: cross-asset measured evidence, evidence gate, research-quality audit, A→B guard
- V1/main/B: unchanged

| Area | Status |
|---|---|
| ENGINEERING ARCHITECTURE | **PASS** |
| DATA INTEGRITY | **PASS with residuals** |
| RELEASE EVIDENCE | **PASS** for test proof + local scan evidence; **portable scan replay not available** |
| V1 REGRESSION | **PASS** |
| RESEARCH CONTRACT | **PASS** |
| HYPOTHESIS QUALITY | **PARTIAL** — structured hypotheses, but 0 research candidates under the measured-evidence gate |
| DISCOVERY VALUE | **NOT VALIDATED** |
| A-B INTEGRATION | **PARTIAL** — eligibility guard; 0 current eligible candidates, no task/`ok_valid` |
| CI CROSS-OS | **PASS** — GitHub Actions run 20 (`43686642240`, `0d5d6ac`, 230 tests) SUCCESS; run 19 also SUCCESS |

## Phase 1 evidence
- Verified scan: `scan-20261115T044634Z-b68802`, 358,310 prices, 159,508 indicators, 1,506 anomalies,
  5 transmissions, 11 opportunities; config/data hashes recomputed; report/scan-json/pipeline
  frozen hashes verified; all output columns fingerprinted.
- Adversarial cases: empty/fake/stale/partial/missing/mismatched/OHLCV/output/artifact modifications
  rejected; valid real scan accepted.
- Test proof: 230/230; independent final QA G PASS and H PASS WITH ISSUES (P2 only); earlier P1s fixed.
- Accepted residuals: local DB/report/exports not in git; synthetic-consistent DB trust boundary;
  fabricated ingest-run row; artifact-vs-DB cross-check; CI unexecuted; no licensed consensus/OIS.

## Phase 2 evidence
- Cross-asset global/local/FX regressions produce measured discriminating evidence; evidence gate
  requires >=2 open hypotheses with such evidence.
- Current: 20 candidates -> 0 research / 20 intelligence (`evidence_gap`); N225 has one strong local
  fit, not two. No candidate is deleted or handed to B.
- Research-quality audit separates selection/question/evidence/decision; mean measured coverage 0.075;
  no duplicate claims. See `evaluation/RESEARCH_QUALITY_AUDIT.md`.
- A→B: only `evidence_ok` tiers can hand off; current no eligible candidate, so no task is created.
- DISCOVERY VALUE: NOT VALIDATED — no human labels, no independent future window; selection
  comparison D 1.000 < C 1.500 on the reused 2025 window.

## Stop state
**ENGINEERING ACCEPTED (Phase 1, with explicit P2 residuals)**  
**PHASE 2: PARTIAL / RESEARCH NOT VALIDATED**  
**CI CROSS-OS: BLOCKED**

## Phase-2 independent QA
- `audit/PHASE2_QA_ENGINEERING.md`: PASS WITH ISSUES; sole P1 was the uncommitted documentation
  worktree (fixed by the freeze commit); scan gate/proof/230 tests verified.
- `audit/PHASE2_QA_RESEARCH.md`: PASS WITH ISSUES (P2 only); A→B guard end-to-end exit 3; quality
  audit recomputed exactly; no P0/P1; DISCOVERY VALUE NOT VALIDATED.
- P2 notes: quality-audit metric names/denominators are descriptive, not validated; no CLI-level
  handoff test; no independent human labels or fresh future window.


## Final QA (P1 round)
- `FINAL_ENG_P1_QA.md`: PASS, no P0/P1. CI runs 19/20 green; stable IDs and curve identity verified.
- `FINAL_RESEARCH_P1_QA.md`: PASS, no P0/P1. 20/20 contract; research 0/watch4/archive16; handoff 0; DISCOVERY NOT VALIDATED.
- P2 residuals: queue/eligibility are tier-collinear until a B-capability gate is added; local scan evidence not portable; consensus/term-OIS unavailable; CI clean step removes all ignored files (ephemeral runner only).
