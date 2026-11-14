# ACCEPTANCE CONTRACT

## Freeze protocol
1. Requirements → architecture contract → acceptance tests → implementation.
2. Freeze a commit; record code hash, config_hash, data_hash, scan_id, a machine-verifiable test proof (exit code, passed/failed counts, log SHA-256, commit) and artifact hashes. Caller-supplied test counts are not accepted.
3. Independent QA reviews the frozen commit/data snapshot only; it may not edit the audited tree.
4. Findings require a failing reproduction; fixes go to a new commit; re-freeze and re-QA.
5. At least two independent QA passes with new fault inputs and no new P0/P1 for engineering sign-off.

## Splits
- Development: dates/cases used to build V2 rules.
- Validation: dates used to compare A/B/C/D once.
- Test: completely held-out dates, never used for rule changes. If unavailable, report NOT VALIDATED.

## Gates
1 Data Integrity; 2 Quantitative Correctness; 3 Engineering Reliability; 4 Research Methodology;
5 Opportunity Discovery; 6 Integration & Independent QA.

Engineering acceptance requires no P0/P1 and reproducible evidence. Research acceptance requires
independent evidence that D beats simple baselines; otherwise `DISCOVERY VALUE: NOT VALIDATED`.
