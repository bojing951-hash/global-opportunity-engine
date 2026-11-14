# V2 FINAL ACCEPTANCE — contract-driven refactor

- Branch: `architecture/research-v2` (from frozen V1 `1f2b341`, tag `v1-frozen-1f2b341`)
- V1 preserved: tag + `audit/V1_FREEZE.md`; V1 code/scoring not overwritten.
- Tests: 166 offline passed (1 slow real-data V2 test skipped by default); 9 network unchanged.
- Real V2 triage: 5 structured research candidates; top N225 (A), QQQ (B), TAIEX (B), XLV (B), EEM (B).
- V2 blind evaluation: 48 objects, 4 methods; the 2021 date was reused after a gate change, so there is **no independent test split**; result is NOT VALIDATED.

## Required statuses
| Area | Status | Evidence |
|---|---|---|
| EXECUTION ARCHITECTURE | **PASS with issues** | `contracts/` seven contracts, `goe/contracts.py`, `docs/AGENT_OPERATING_MODEL.md`, freeze gate `goe/release.py`, V1 tag, branch, contract tests |
| DATA ARCHITECTURE | **PASS with residuals** | data/time contract; completed-bar DST rule; critical data contract; per-market/curve checks; residual publication/vintage/roll limitations |
| RESEARCH CONTRACT | **PASS with issues** | `contracts/RESEARCH_CONTRACT.md`; ResearchCandidate schema validator; >=2 hypotheses, evidence classes, unknowns, falsifiers, cost/decision impact; contract tests |
| ENGINEERING VALIDATION | **PASS with issues** | 166 offline tests; contract tests; real scan/triage; fault/rollback suites from V1; independent engineering QA found P1s that were fixed; verification reports are `V2_FINAL_QA_ENGINEERING.md` and `V2_FINAL_VERIFICATION_ENGINEERING.md` |
| RESEARCH METHODOLOGY | **PARTIAL** | competing hypotheses/unknowns/falsifiers now explicit; expectation data still proxies; V2 selection not proven better |
| DISCOVERY VALUE | **NOT VALIDATED** | final rater D 0.833 vs C 0.979/B 0.917/A 0.875; the only held-out candidate date was reused after a gate change, so no independent test remains; second rater D 1.350 → instability. No tuning. |
| A→B INTEGRATION | **PARTIAL** | fact-only V2 brief; latest real run B returned `rejected`, A persisted `not_completed:rejected` (never success); no real `ok_valid`; V2 CLI entry exists via `goe triage --handoff` |

## V2 blind evaluation (final)
- 4 dates: 2022-10-31, 2023-03-31, 2024-09-30 (development), 2021-12-31 (exploratory/reused).
- Same facts/as-of; method labels hidden; IDs shuffled; independent LLM rater.
- Full sample: A .875, B .917, C .979, D .833. Reused 2021: A .833, B .583, C .583, D .750, P@3 all zero.
- With no independent test, `DISCOVERY VALUE: NOT VALIDATED` by construction; D does not beat C/B on the full sample.
- The earlier exploratory rating gave D 1.350; it did not replicate (0.833). This is reported, not hidden.
- Why: cards measure asset selection, not D's research brief; D is pre-gated while A/B/C are not; reused-date D n=3; single LLM/no human labels. See `audit/RESEARCH_V2_RESULTS.md`.

## A→B actual behavior
V2 fact-only question for N225 produced downstream `run_ok` false/rejected; A persisted
`not_completed:rejected` and kept the candidate. No fake end-to-end success. B's limitations are
external; B was not modified.

## Verification status
Independent engineering verification: PASS WITH ISSUES; the anomaly date semantics P1 is resolved by
the explicit DETECTION_CONTRACT definition (`date` = detection/decision date, macro
`evidence.observation_date` = reference period; recency never uses an unpublished observation).
Research verification: P1 documentation stale items corrected; no independent test split remains,
so discovery value stays NOT VALIDATED.

## Residuals
- Macro/vintage publication times and futures rolls unavailable; futures flagged only.
- V2 priorities are ordinal rules, not an empirically validated ranking.
- No human/expert labels; no future out-of-sample window; no return implication claimed.
- V2 CLI handoff persistence is via `goe.integration.research_handoff` (not yet a first-class CLI subcommand).
