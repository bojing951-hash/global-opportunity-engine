# V2 FINAL ACCEPTANCE — contract-driven refactor

- Branch: `architecture/research-v2` (from frozen V1 `1f2b341`, tag `v1-frozen-1f2b341`)
- V1 preserved: tag + `audit/V1_FREEZE.md`; V1 code/scoring not overwritten.
- Tests: 165 offline passed (1 slow real-data V2 test skipped by default); 9 network unchanged.
- Real V2 triage: 5 structured research candidates; top N225 tier A/B, then DXY/BRL/USDJPY/TAIEX.
- V2 blind evaluation: 48 objects, 4 methods; result **NOT VALIDATED** (see below).

## Required statuses
| Area | Status | Evidence |
|---|---|---|
| EXECUTION ARCHITECTURE | **PASS** | `contracts/` seven contracts, `goe/contracts.py`, `docs/AGENT_OPERATING_MODEL.md`, freeze gate `goe/release.py`, V1 tag, branch, contract tests |
| DATA ARCHITECTURE | **PASS with residuals** | data/time contract; completed-bar DST rule; critical data contract; per-market/curve checks; residual publication/vintage/roll limitations |
| RESEARCH CONTRACT | **PASS** | `contracts/RESEARCH_CONTRACT.md`; ResearchCandidate schema validator; >=2 hypotheses, evidence classes, unknowns, falsifiers, cost/decision impact; contract tests |
| ENGINEERING VALIDATION | **PASS with issues** | 165 offline tests; contract tests; real scan/triage; fault/rollback suites from V1; no P0/P1 known after final QA (see `V2_FINAL_QA.md`) |
| RESEARCH METHODOLOGY | **PARTIAL** | competing hypotheses/unknowns/falsifiers now explicit; expectation data still proxies; V2 selection not proven better |
| DISCOVERY VALUE | **NOT VALIDATED** | final rater D 0.833 vs C 0.979/B 0.917/A 0.875; test P@3 all 0; second rater D 1.350 → inter-rater instability. No tuning on test. |
| A→B INTEGRATION | **PARTIAL** | fact-only V2 brief; B returns `unmapped/no_registry_identity`; A persists `not_completed`, never success; no real `ok_valid` |

## V2 blind evaluation (final)
- 4 dates: development 2022-10-31/2024-09-30, validation 2023-03-31, test 2021-12-31.
- Same facts/as-of; method labels hidden; IDs shuffled; independent LLM rater.
- Full sample: A .875, B .917, C .979, D .833. Test: A .833, B .583, C .583, D .750, but P@3 = 0 for all.
- D does not beat B/C on both mean and P@3 on the test; `DISCOVERY VALUE: NOT VALIDATED`.
- The earlier exploratory rating gave D 1.350; it did not replicate (0.833). This is reported, not hidden.
- Why: cards measure asset selection, not D's research brief; D is pre-gated while A/B/C are not; test n=3; single LLM/no human labels. See `audit/RESEARCH_V2_RESULTS.md`.

## A→B actual behavior
V2 fact-only question for N225 produced downstream `run_ok=true` but S8 `no_registry_identity`; A records
`not_completed:<semantic>` and keeps the candidate. No fake end-to-end success. B's limitations are
external; B was not modified.

## Residuals
- Macro/vintage publication times and futures rolls unavailable; futures flagged only.
- V2 priorities are ordinal rules, not an empirically validated ranking.
- No human/expert labels; no future out-of-sample window; no return implication claimed.
- V2 CLI handoff persistence is via `goe.integration.research_handoff` (not yet a first-class CLI subcommand).
