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
| V2-08 | P1 | evaluation measures asset cards rather than D's research questions; D prefiltered; test n=1 | disclosed; protocol amended as a limitation; result remains NOT VALIDATED; future evaluation needs common research-brief template and larger held-out sample | OPEN (research limitation) |
| V2-09 | P1 | V2 handoff not wired to CLI; timeout persisted as unknown | module contract + persistence; CLI integration remains a V3 item; timeout label preserved in result | PARTIAL |
| V2-10 | P2 | duplicate/identical cards, no CI, single LLM rater | documented; no false `VALIDATED` claim | OPEN (research limitation) |

## Current V2 verdict
EXECUTION ARCHITECTURE: PASS after V2-01/02 fixes (pending independent re-QA).
DATA ARCHITECTURE: PASS with residuals.
RESEARCH CONTRACT: PASS (executable + tests), but discovery value is **NOT VALIDATED**:
final rater D 0.833 vs C 0.979/B 0.917/A 0.875; test P@3 all zero; a second rater had D 1.350,
showing inter-rater instability. The evaluation measures asset cards, not D's research brief.
