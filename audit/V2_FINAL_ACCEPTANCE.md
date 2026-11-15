# V2 FINAL ACCEPTANCE — contract-driven refactor

- Branch: `architecture/research-v2` (from frozen V1 `1f2b341`, tag `v1-frozen-1f2b341`); final code `a20ce29`, proof commit `168291d`, manifest `release_a20ce293f4.json`.
- V1 preserved: tag + `audit/V1_FREEZE.md`; V1 code/scoring not overwritten.
- Tests: **209 offline passed**, 10 network/real-data deselected by default; verified test proof + rerun 209.
- Real V2 triage after the evidence gate: **0 research candidates + 20 intelligence (evidence_gap)**; all 20 pass the research contract. No candidate is deleted or handoff-forced.
- V2 blind evaluation: 48 objects, 4 methods; the 2021 date was reused after a gate change, so there is **no independent test split**; result is NOT VALIDATED.

## Required statuses
| Area | Status | Evidence |
|---|---|---|
| EXECUTION ARCHITECTURE | **PASS** | `contracts/` seven contracts, `goe/contracts.py`, `docs/AGENT_OPERATING_MODEL.md`, freeze gate `goe/release.py`, V1 tag, branch, contract tests |
| DATA ARCHITECTURE | **PASS with residuals** | data/time contract; completed-bar DST rule; critical data contract; per-market/curve checks; residual publication/vintage/roll limitations |
| RESEARCH CONTRACT | **PASS** | `contracts/RESEARCH_CONTRACT.md`; ResearchCandidate schema validator; >=2 hypotheses, evidence classes, unknowns, falsifiers, cost/decision impact; contract tests |
| ENGINEERING VALIDATION | **PASS** | fresh clone 209 passed/10 deselected; real test-proof release gate; V2 lifecycle/orphan/FK tests; independent red-team found P1s that were fixed |
| RESEARCH METHODOLOGY | **PARTIAL** | competing hypotheses/unknowns/falsifiers now explicit; expectation data still proxies; V2 selection not proven better |
| DISCOVERY VALUE | **NOT VALIDATED** | exploratory 2025-12-31 (already used in V1 cases, not independent): D 1.000 vs C 1.500/B 0.917/A 1.083, P@3 D 0.00; earlier reused 2021 data also D 0.833 < C 0.979. Research-question quality still unmeasured; no tuning. |
| A→B INTEGRATION | **PARTIAL** | fact-only V2 brief; latest real run B returned `refused` (S8 no_registry_identity), A persisted `not_completed:refused` (never success); no real `ok_valid`; V2 CLI `goe triage --handoff` works. An earlier run failed at process level and is now mapped to `error`, not B rejection. |

## V2 blind evaluation (final)
- 4 dates: 2022-10-31, 2023-03-31, 2024-09-30 (development), 2021-12-31 (exploratory/reused).
- Same facts/as-of; method labels hidden; IDs shuffled; independent LLM rater.
- Full sample: A .875, B .917, C .979, D .833. Reused 2021: A .833, B .583, C .583, D .750, P@3 all zero.
- With no independent test, `DISCOVERY VALUE: NOT VALIDATED` by construction; D does not beat C/B on the full sample.
- The earlier exploratory rating gave D 1.350; it did not replicate (0.833). This is reported, not hidden.
- Why: cards measure asset selection, not D's research brief; D is pre-gated while A/B/C are not; reused-date D n=3; single LLM/no human labels. See `audit/RESEARCH_V2_RESULTS.md`.

## A→B actual behavior
V2 fact-only question for N225 produced downstream `run_ok` false/refused
(S8 `no_registry_identity`); A persisted `not_completed:refused` and kept the candidate. No fake
end-to-end success. B's limitations are
external; B was not modified.

## CI delivery
`.github/workflows/verify-release.yml` replays the latest proof on ubuntu-latest/Python 3.12.
The workflow is committed; **it has not been executed on GitHub Actions in this session**, so
cross-OS execution remains unverified until the branch is pushed and the run completes.

## Evidence gate (2026-11-15)
Implemented: cross-asset factor regression evidence (active), file-backed consensus/policy-curve
adapters (PIT, no fabrication), and a measured-evidence gate. Real result: 0 research candidates,
20 intelligence. Every candidate has fewer than two measured discriminating hypotheses with the
currently available evidence. OIS is a public policy-path proxy, not term OIS; consensus is BLOCKED by
the absence of a licensed public history. See `docs/EVIDENCE_SOURCES.md`.

Measured discriminating evidence is required in >=2 open hypotheses; with current data only N225
qualifies. The other 19 are retained as intelligence, not deleted. Details:
`audit/EVIDENCE_GATE_DECISION.md`, `docs/EVIDENCE_SOURCES.md`.

## Independent final QA
- `audit/FINAL_RELEASE_QA.md`: PASS WITH ISSUES, no P0/P1 (release proof, attack matrix, fresh clone).
- `audit/FINAL_RESEARCH_QA.md`: PASS WITH ISSUES, no P0/P1, DISCOVERY VALUE NOT VALIDATED (P2 wording only).

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
