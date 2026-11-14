# FINAL INDEPENDENT RESEARCH QA — frozen 168291d (code a20ce29)

- Date: 2026-11-15 (Asia/Hong_Kong)
- Scope: read-only audit; only this file written. `HEAD=168291de09ec...`; no `*.py` diff vs `168291d`.
- Verdict: **PASS WITH ISSUES (P2 only)**; **DISCOVERY VALUE: NOT VALIDATED**; no new P0/P1.

## 1. 20 candidates / contract / evidence integrity — PASS

- `evaluation/v2_candidates_20_2026-11-13.json`: 20 candidates, schema `research-candidates/v2`, as_of 2026-11-13.
- `goe.contracts.validate_research_candidate`: **20/20 pass, 0 ContractError**.
- Untestable hypotheses with `evidence_for`: **0** (57 untestable, 47 open; all statuses legal).
- No untestable hypothesis evidence leaked into candidate-level `evidence_for`: **0** matches.
- `H-ENER-CRACK` (RC-20261113-04): status `open` (was illegal `obtainable`), has falsifier `裂解价差与库存` / data `crack/inventory`; no longer the "evidence/no test/non-open" contradiction.
- CN availability (RC-20261113-07): `H-SECCE-STYLE` falsifier data is `local rates` with status `obtainable`; candidate evidence carries no `UST available` claim. Region != US no longer gets unconditional `UST available` in `goe/hypotheses.py`.
- No evidence `available_at` after `as_of` (validator enforces; passes).

## 2. Structural diversity / statuses / SLV — PASS (P2 residue)

- Distinct per-candidate `{(hypothesis id,type,status)}` signatures: **18**; distinct falsifier signatures: **18** (both >=10). 104 hypotheses, IDs namespaced by phenomenon.
- Note: if signatures are reduced to type/status only, diversity is 8 (duplicates among US equity and agriculture). The >=10 result depends on the project's ID-inclusive signature definition.
- No invalid status anywhere (`open`/`untestable` only).
- SLV (RC-20261113-05): `H-SILV-ART` = `untestable`, `evidence_for=[]`, label now `拆股/盘中/陈旧数据伪影` (not futures/roll); no `futures`/换月 evidence in candidate. **P2 residue**: implications and evidence_against still say `换月日附近跳变` / `未记录换月/清洗问题`.

## 3. Evaluation docs — PASS on required statements (P2 wording)

- `audit/RESEARCH_V2_RESULTS.md:32`: "Additional exploratory window (2025-12-31; already used in V1 cases, not independent)"; D **1.000** vs C **1.500**, P@3 0.00; `DISCOVERY VALUE: NOT VALIDATED`.
- `evaluation/RESEARCH_EVALUATION_PROTOCOL.md:65-68`: 2025-12-31 not a future window / selection-quality check; A 1.083 / B 0.917 / C 1.500 / D 1.000; D does not beat C; NOT VALIDATED.
- `evaluation/V2_EVALUATION_RESULTS.md`: "Independent test split — NOT AVAILABLE", exploratory, NOT VALIDATED. No held-out or live-test-split claim found.
- **P2**: protocol section heading still says "New frozen window"; text does not literally say "exploratory/not independent" (semantically equivalent: not future, selection-quality only, not reused).

## 4. A→B actual behavior — PASS

- `data/goe.db`: `research_v2_tasks` status `not_completed:refused`; latest `research_v2_results` row `semantic_status=refused` (S8 `no_registry_identity`), earlier row `rejected`; both `run_ok` column 0.
- Candidate `RC-20261113-12` retained in `research_v2_candidates` (20 rows).
- `V2_FINAL_ACCEPTANCE.md:18,29-30` states refused/not_completed and "no fake end-to-end success"; no `ok_valid` success claim.
- **P2**: acceptance says earlier process-level failure "mapped to error", but DB row 1 is `rejected`; latest refused payload has `run_ok:true` inside `result` while column/status are 0/not_ok. No success claim, but wording/field consistency issue.

## 5. New P0/P1 — none

- The two targeted P1s from `audit/QA_V2_RESEARCH_CLOSURE.md` are resolved at a20ce29: H-CRACK illegal status/leak (P1-N1) and CN sector UST availability (P1-R1, CN scope).
- P0: none. New P1: none. Residual P2s: protocol "frozen window" heading; SLV rollover wording in implications/evidence_against; commodity `DXY/UST 可用` wording (pre-existing, outside targeted CN scope); stale counts in `audit/V2_FINAL_ACCEPTANCE.md` (166 tests / 15 signatures vs current 179 / 18).
- No code changes: `git diff 168291d -- '*.py'` empty; only pre-existing `M audit/V2_FINAL_ACCEPTANCE.md` in worktree, plus this new audit file.

**DISCOVERY VALUE: NOT VALIDATED.** No independent test split; D 1.000 < C 1.500 on the exploratory 2025-12-31 window; no tuning on reused dates.
