# V2 issue ledger (contract review + method review → fixes)

| ID | Severity | Finding | Fix | Status |
|---|---|---|---|---|
| V2-01 | P0 | V2 files untracked; branch HEAD was V1; QA could not checkout | committed all V2 files on `architecture/research-v2` | FIXED |
| V2-02 | P0 | `release.py` allowed dirty tree and empty evidence | requires clean tree, successful scan, test_count, writes artifact hashes, refuses overwrite | FIXED |
| V2-03 | P1 | macro anomaly evidence lacked observation_date | emit_rows adds `observation_date` for macro/valuation | FIXED |
| V2-04 | P1 | key UST tenors checked for presence, not freshness | required 2Y/10Y must be <=15 days old | FIXED |
| V2-05 | P1 | research schema missed evidence_for/against, evaluation id, source/future checks, positive hours | contract validator + fields added | FIXED |
| V2-06 | P1 | priority rule was dead code/weighted; H3 always open; falsifiers generic | ordinal M/G/D/I rules; H3 requires usable positioning; falsifiers use candidate-specific thresholds | FIXED |
| V2-07 | P1 | V1 comparison metadata null (`DataFrame` iteration) | `.to_dict("records")` | FIXED |
| V2-08 | P1 | evaluation measures asset cards rather than D's research questions; D prefiltered; the 2021 date was reused (no independent test) | disclosed; protocol amended as a limitation; result remains NOT VALIDATED; future evaluation needs a common research-brief template and a new future test window | OPEN (research limitation) |
| V2-09 | P1 | V2 handoff not wired to CLI; timeout persisted as unknown | `goe triage --handoff`, timeout/id/L1 semantics implemented and verified | FIXED |
| V2-10 | P2 | duplicate/identical cards, no CI, single LLM rater | documented; no false `VALIDATED` claim | OPEN (research limitation) |

## Current V2 verdict
EXECUTION ARCHITECTURE: PASS after V2-01/02 fixes (pending independent re-QA).
DATA ARCHITECTURE: PASS with residuals.
RESEARCH CONTRACT: PASS (executable + tests), but discovery value is **NOT VALIDATED**:
final rater D 0.833 vs C 0.979/B 0.917/A 0.875; the 2021 date was reused after a gate change
(no independent test remains); a second rater had D 1.350, showing inter-rater instability. The
evaluation measures asset cards, not D's research brief.

## Round-4 autonomous repair ledger (2026-11-14)
| ID | Severity | Finding | Root cause | Fix / evidence | Status |
|---|---|---|---|---|---|
| P1-A | P1 | fresh clone `pytest tests` failed on `data/goe.db` | contract test implicitly opened developer DB; default pytest ran network tests | synthetic anomaly contract test; `realdata` marker; default excludes network/realdata; no-`data` clone 176 passed/10 deselected | FIXED |
| P1-B | P1 | release manifest accepted caller `test_count=9999` | counts were arguments, not evidence | `run_test_proof` executes pytest, logs stdout, SHA-256, commit, clean tree; gate cross-checks counts/log, rejects stale/forged, re-executes suite during manifest creation; logs committed (`.gitignore` exception) | FIXED |
| P1-C | P1 | 12/12 candidates used the same five hypotheses | fixed template in triage | `goe/hypotheses.py` by asset class/subtype/region/detector/data availability; 20 real candidates now 15 hypothesis signatures / 5 decision-impact variants; untestable hypotheses cannot contribute supporting evidence; tests require ≥2 distinct falsifier hypotheses and one available test | FIXED (semantic quality still reviewed) |
| P1-D | P1 | RC-* tasks/events were invalid V1 references | reused V1 tables | `research_v2_candidates/hypotheses/evidence/tasks/events/results`, FKs/lifecycle, legacy migration, orphan counters; real handoff keeps candidate, task/result linked, all counters zero | FIXED |
| P1-E | P1 | process-level handoff failure was labelled `rejected` (B refusal) | parser mapped `run_ok=false` without checking rc/report | no report + rc!=0 -> semantic `error`; absolute out_dir; real run now `refused/not_completed:refused`, retaining candidate | FIXED |
| P1-F | P1 | evaluation gate could call a reused/exploratory window `VALIDATED` with n≥3 | only mean/P@3 checked | 2025-12-31 marked exploratory (used in V1 case); no independent test; result NOT VALIDATED. Future protocol requires a genuinely new window and human/expert labels. | OPEN (research limitation) |

### Remaining non-blocking limitations
- No human/expert research-quality labels; single LLM rater; V2 question quality is not measured by the asset-card protocol.
- No genuinely future out-of-sample window; 2025-12-31 was in a V1 validation case.
- Market data publication vintages/rolls remain unavailable; expectation proxies are not consensus.
- V2 hypotheses are reasoner-generated from templates + evidence; they are not a substitute for B's deep research.

| P1-G | P1 | release proof accepted a shell command and rename could hide a dirty code file | proof command validation was substring-based; dirty parser ignored rename destination | direct `python -m pytest tests` only, no `-c`; rename destination checked; rerun counts must match proof; tests reproduce both attacks | FIXED |
| P1-H | P1 | untestable hypotheses leaked supporting evidence; 20 candidates only 7 structural signatures; SLV treated as futures | unconditional evidence + generic IDs | untestable evidence empty; phenomenon namespaces; 18 structural signatures; all 20 candidates pass the research contract; futures-only artifact test; tests cover all asset classes | FIXED |
