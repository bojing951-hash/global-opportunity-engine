# FINAL ACCEPTANCE — Phase 1 engineering freeze

- Date: 2026-11-15
- Branch: `architecture/research-v2`
- Frozen code: `9d51769`; release proof `release_9d51769823.json` (219/219 tests);
  verified scan `scan-20261115T044634Z-b68802`
- HEAD after this report: docs-only descendant
- V1: tag `v1-frozen-1f2b341`; main untouched

## Final status
| Area | Status |
|---|---|
| ENGINEERING ARCHITECTURE | **PASS** |
| DATA INTEGRITY | **PASS with residuals** |
| RELEASE EVIDENCE | **PASS** (scan evidence + v4 test proof) |
| V1 REGRESSION | **PASS** |
| RESEARCH CONTRACT | **PASS** |
| HYPOTHESIS QUALITY | **PARTIAL** |
| DISCOVERY VALUE | **NOT VALIDATED** |
| A-B INTEGRATION | **PARTIAL** |
| FINAL | **ENGINEERING ACCEPTED; RESEARCH NOT VALIDATED; CI CROSS-OS BLOCKED** |

## Evidence
- Test proof: 219 passed = 219 executed = required; 0 failed/skipped; `verify-release` accepted.
- Real scan evidence: 358,310 prices; 159,508 indicators; 1,506 anomalies; 5 transmissions;
  11 opportunities; config/data hashes recomputed; readiness/core series/source provenance checked;
  all output columns and scan-time artifact hashes verified.
- Adversarial cases rejected: empty DB, fake success, fake config/data hash, same-row OHLCV change,
  output field change, stale/future as_of, next-day fetched_at abuse, partial ingest, missing/
  mismatched report/scan-json/pipeline, fake artifact hash.
- Independent QA: QA_SCAN_FINAL_G **PASS**; QA_SCAN_FINAL_H **PASS WITH ISSUES** (P2 docs/CI only).
  Earlier C/D/E/F P1s were fixed; two clean final passes (G/H) have no P0/P1.
- V1/main unchanged; B not modified.

## Research status
Research evidence gate is implemented: only candidates with >=2 open hypotheses carrying **measured**
discriminating evidence remain research candidates. Current real result: **0 research candidates,
20 intelligence**; N225 has one strong local fit but not two. No independent human labels/future
window; `DISCOVERY VALUE: NOT VALIDATED`. Consensus feed is blocked (no licensed source); OIS is a
policy-path proxy, not term OIS.

## Accepted residuals (P2)
1. Scan evidence depends on local DB/reports/exports (gitignored); fresh clone verifies test proof only.
2. A self-consistent synthetic DB is inside the trust boundary.
3. Fabricated in-window ingest run can satisfy the live-ingest check.
4. Artifact-vs-DB is not fully cross-checked; frozen hashes stop file edits, not coordinated DB forgery.
5. GitHub Actions has not run; Docker cross-OS failed on Keychain credentials.
6. No licensed consensus/term-OIS; research output is zero by design until data or gate policy changes.

## Stop state
**ENGINEERING ACCEPTED (with explicit P2 residuals)**  
**DISCOVERY VALUE: NOT VALIDATED**  
**CI CROSS-OS: BLOCKED / UNVERIFIED**
