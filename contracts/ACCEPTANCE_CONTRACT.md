# ACCEPTANCE CONTRACT

## Freeze protocol
1. Requirements → architecture contract → acceptance tests → implementation.
2. Freeze a commit; record code hash, config_hash, data_hash, scan_id, a machine-verifiable test proof and artifact hashes.
   Test proof contract (`goe-test-proof/v2`, enforced by `goe/release.py`):
   - The caller cannot supply a pytest command; the gate builds the canonical full-suite invocation itself.
   - Any argv that is not byte-equal to the canonical template is rejected (`--ignore`, `--ignore-glob`, `--deselect`, `-k`, marker overrides, `-c`, `-p`, `-o addopts=...`, positional node ids).
   - Pytest environment overrides (`PYTEST_ADDOPTS`, `PYTEST_PLUGINS`, `PYTEST_CFG`, `PYTEST_DEBUG`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD`) are cleared.
   - The **collected** node-id set at the frozen commit must equal the **executed** node-id set in JUnit evidence; a minimum count per category (`offline`/`network`/`realdata`) blocks silent shrinkage.
   - The proof stores a `{python}`/`{junit}` command template and repo-relative evidence paths only, so a fresh clone on another machine can replay it.
   - A release manifest requires the `offline` category and is created only after the gate **re-executes** the suite; a forged proof file cannot satisfy the rerun.
   Caller-supplied test counts and hand-written success flags are not accepted.
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
