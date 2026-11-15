# FINAL ACCEPTANCE — current branch state

- Date: 2026-11-15
- Branch: `architecture/research-v2`
- Engineering baseline: code `9d51769` + Phase-1 proof `release_9d51769823.json` (219 tests)
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
| A-B INTEGRATION | **PARTIAL** — eligibility guard; 0 current eligible candidates, no `ok_valid` |
| CI CROSS-OS | **BLOCKED / UNVERIFIED** — workflow exists, never executed on GitHub; Docker blocked by Keychain |

## Phase 1 evidence
- Verified scan: `scan-20261115T044634Z-b68802`, 358,310 prices, 159,508 indicators, 1,506 anomalies,
  5 transmissions, 11 opportunities; config/data hashes recomputed; report/scan-json/pipeline
  frozen hashes verified; all output columns fingerprinted.
- Adversarial cases: empty/fake/stale/partial/missing/mismatched/OHLCV/output/artifact modifications
  rejected; valid real scan accepted.
- Test proof: 219/219; independent final QA G PASS and H PASS WITH ISSUES (P2 only); earlier P1s fixed.
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
