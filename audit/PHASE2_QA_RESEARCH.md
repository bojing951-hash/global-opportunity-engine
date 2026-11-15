# PHASE 2 — INDEPENDENT RESEARCH QA (research tracks)

- Date: 2026-11-15
- Frozen HEAD: `3c640dd` (code `671f5fa`), branch `architecture/research-v2`
- Scope: A→B eligibility guard, research-quality audit, discovery claims, A/B/C/D evaluation history,
  new-window reuse, new P0/P1. Read-only; this file is the only write. Timebox 6 min.
- Method: source/test reading + DB queries (`data/goe.db`) + independent recomputation from
  `exports/research_candidates_2026-11-13.json` + targeted tests + a CLI reproduction on a DB copy.
- Full offline suite completed with exit 0 (`pytest tests -m "not network"`, background); targeted
  research tests 12/12 passed. CLI reproduction on `/tmp/goe_qa.db`: **exit 3**, 0 tasks, 20
  intelligence (3m32s runtime, mostly feature build).

## Verdict: **PASS WITH ISSUES** (P2 only)

**Remaining P0: 0. Remaining P1: 0.**

**DISCOVERY VALUE: NOT VALIDATED** — unchanged, and correctly stated everywhere reviewed.
The 20→0 candidate result is an honest gate output, not evidence of discovery value.

## 1. A→B eligibility guard — correct; E2E test missing (P2)

- Code is correct: `goe/integration/research_handoff.py:95-104` admits only
  `priority_tier in (A,B,C)` **and** `research_readiness == "evidence_ok"`; intelligence and
  `evidence_gap` are excluded. `goe/cli.py:319-329` computes the eligible set, prints the retention
  message and returns **3 before** `IAAdapter`/`handoff_v2`, so no task is created and no B call occurs.
  `main()` propagates the return code (`goe/cli.py:582`, `raise SystemExit(main())`).
- `run_triage` returns `ranked + intelligence` (`goe/research_triage.py:291`), so `eligible[0]` is the
  highest-ranked eligible candidate, not build order.
- Tests: `tests/test_research_v2.py:184-192` covers the helper predicate, including exclusion of
  intelligence and B/`evidence_gap`. There is **no CLI-level test** asserting exit 3, zero
  `research_v2_tasks`, and retained candidates. This is a coverage gap, not an observed failure (P2).
- DB/artifact: `research_v2_candidates` = 20, all `intelligence`; `research_v2_tasks` = 0,
  `research_v2_results` = 0, `research_v2_events` = 0. Export
  `exports/research_candidates_2026-11-13.json` = 20 × (`intelligence`, `evidence_gap`). No task was
  created for the current 0-eligible state. `priority_rank` is 0 for intelligence (not ranked), as designed.
- **Reproduced** on a copy (`triage --db /tmp/goe_qa.db --handoff --out /tmp/goe_qa_out`): exit code **3**,
  message "no eligible research candidate ...", `research_v2_tasks` stayed **0**, candidates stayed
  **20 intelligence**. The guard is effective end-to-end, not only in the helper unit test.

## 2. Research-quality audit — real separation, but two descriptive metrics mislead (P2)

- `goe/research_quality.py` is not a single score and invents no human labels: it reports selection
  (importance/gap), question structure (distinct types + available tests), evidence (measured
  discriminating hypotheses, coverage, duplicate claims), and a decision-value flag. It hard-codes
  `discovery_value: "NOT VALIDATED"` (`:66`) and states it is descriptive (`:67-68`).
- Independent recomputation from the current export reproduces the committed artifact
  `evaluation/research_quality_audit.json` and `evaluation/RESEARCH_QUALITY_AUDIT.md` exactly:
  20 candidates, 0 research, 0 with ≥2 measured discriminating, **mean coverage 0.075**,
  4 decision-value flags, 0 duplicate claims, mean question structure 0.988.
- Measured-evidence counting is correctly restricted to `status=open` + `discriminating=true` +
  `class != unknown` (`:27-29`), matching the gate in `contracts.py:132-138` and
  `research_triage.py:269`. Duplicate claim counting is exact-string reuse across hypotheses
  (`:32-33`) and the test proves duplicates are exposed, not rewarded (`tests/test_research_quality.py:33-37`).
- **P2-a:** `decision_value_flag` is true for 4/20 candidates that all have **0 measured
  discriminating evidence** (RC-12/14/15/19; RC-15 has only 1 open hypothesis). The formula
  (`:40`) uses importance × gap × an available test and never requires evidence or a research tier.
  It is defined as descriptive, but the name invites being quoted as "4 candidates have decision
  value" alongside "0 research". Rename (e.g. `decision_testability_flag`) or require measured evidence.
- **P2-b:** `question_structure = min(1, distinct_types/4)` saturates (mean 0.988; 19/20 are 1.0),
  so it cannot discriminate question quality. The `/4` denominator is arbitrary and unvalidated.
  It is not used for gating, so this is a descriptive-quality issue only.
- **P2-c:** coverage 0.075 is hypotheses-with-evidence ÷ open hypotheses, not evidence strength or
  count; a strong local fit in one hypothesis can be diluted by several unknowns. Docs state
  "measured coverage", so this is a presentational limitation, not a false claim.

## 3. Docs vs claims — accurate (no claim of progress as validation)

- `evaluation/EVALUATION_PROTOCOL_V3.md:17-25` permits only `DISCOVERY VALUE: NOT VALIDATED` with no
  human/expert labels and no independent future window; tracks are never collapsed into one score;
  current result 20→0 and 0.075 is labelled the honest gate output.
- `docs/EVIDENCE_SOURCES.md:6-7` is accurate on the two contested sources: policy path/OIS is
  **PARTIAL**, explicitly "**Not term OIS**", FRED SOFR/2Y/10Y is a "policy-path proxy" and disabled
  by default; consensus/revisions is **BLOCKED (adapter only)**, no licensed feed, no fabricated
  values. `audit/HYPOTHESIS_DISCRIMINATION.md:23-27` likewise calls the absence an evidence
  limitation and declines to tune the gate on reused dates.
- `audit/FINAL_ACCEPTANCE_CURRENT.md` keeps `DISCOVERY VALUE: NOT VALIDATED` (line 17) and
  "PHASE 2: PARTIAL / RESEARCH NOT VALIDATED"; the current 20→0 result is not presented as progress.
- No document reviewed claims consensus/OIS were obtained, or that 0 research validates the engine.

## 4. A/B/C/D history and new-window reuse — documented; independence is structurally weak

- `evaluation/RESEARCH_EVALUATION_PROTOCOL.md` fixes A/B/C/D, pre-registers the blind-card criteria,
  and explicitly relabels 2021-12-31 **exploratory** because V2 rules changed and the date was reused;
  the decision rule forbids tuning on the test split.
- `evaluation/new_window/RESULTS.md` states 2025-12-31 was already used in a V1 validation case, is
  not independent, is exploratory only, and was not reused after its result. Result D 1.000 < C 1.500
  (P@3 0.00 vs 0.67) → NOT VALIDATED. `audit/RESEARCH_V2_RESULTS.md` repeats that no independent test
  exists and that no weights were tuned on the reused window.
- **P2-d:** `audit/V2_METHOD_REVIEW.md:59` already records that the dev/validation dates overlap the
  V1 blind-rating dates, so even the V2 dev/validation split is not design-independent. This is
  disclosed, but it means no historical A/B/C/D comparison in this repo is a clean test. No evidence
  of return-label or test-set tuning was found; the limitation is design, not observed cheating.

## 5. New research P0/P1

None found. The issues above are P2: missing CLI E2E guard test; misleading `decision_value_flag`
name/threshold; saturated `question_structure`; coverage metric semantics; disclosed but unresolved
split-dependence. Also a non-HEAD workspace observation: uncommitted edits to
`PROJECT_STATE.md`, `audit/FINAL_ACCEPTANCE_CURRENT.md`, `audit/TEST_EVIDENCE.md` change counts
219→222; the uncommitted `TEST_EVIDENCE.md` line still cites commit `9d51769` instead of proof/code
`671f5fa`, a bookkeeping inconsistency to fix before sign-off (not part of frozen HEAD, not P1).

## Explicit status

- **DISCOVERY VALUE: NOT VALIDATED.**
- **ENGINEERING: PASS WITH ISSUES (P2 only).**
- A→B guard: **effective for the current real state** (0 eligible → exit 3 path with no task), with
  only a test-coverage gap.
