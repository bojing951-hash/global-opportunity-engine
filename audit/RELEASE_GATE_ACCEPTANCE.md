# RELEASE GATE ACCEPTANCE — P1-01 / P1-02

- Date: 2026-11-15
- Branch: `architecture/research-v2`
- Scope: the release gate only (`goe/release.py`, its CLI, contract, tests).
  No change to `investment-agent` (V1/B), to the scan pipeline, or to stored research output.

## What was broken

| ID | Defect | Reproduction before the fix |
|---|---|---|
| P1-01 | A release manifest could be built from a **partial test run**. The gate accepted a caller-supplied pytest command; `--ignore` excluded most test files and a 7-test run produced a proof and a manifest. | crafted proof with `--ignore` was accepted (`ACCEPTED_SPOOF`) |
| P1-02 | The proof was **not portable**: it stored an absolute interpreter path (`/Users/cast/.../.venv/bin/python`) and an absolute cwd, so a fresh clone could not replay it. | latest proof at the time contained absolute paths |

## Design after the fix (proof schema v4)

1. **No caller command.** `run_test_proof()` builds the pytest invocation itself; the argv must be
   byte-equal to the canonical template or the proof is rejected.
2. **Collected == executed.** Node ids are collected from the tree, parsed from JUnit and compared as
   sets; `passed == required == executed`, `skipped == 0`, failures/errors rejected.
3. **Executed in the committed tree.** A detached `git worktree` at `HEAD` is materialised, then
   every path is compared to `git ls-tree -r` and every blob re-hashed (SHA-1) so attributes,
   `export-ignore` or smudge filters cannot change what is executed.
4. **No committed test may disappear.** Every `tests/**/test_*.py` in the tree must produce at
   least one collected test (`collect_ignore` filtering is rejected).
5. **Trusted launcher.** `python -c` with `PYTHONSAFEPATH=1`, real pytest imported before the tree
   is prepended, `PYTHONPATH`/`PYTHONHOME`/`PYTHONOPTIMIZE` cleared — a repo-root `pytest.py`,
   `sitecustomize.py` or an installed copy of `goe` cannot hijack the run.
6. **Fail closed.** Any git failure raises; dirty worktrees (including `assume-unchanged`,
   `skip-worktree`) are rejected; release operations require `root == cwd`; evidence paths must be
   repo-relative and inside the root; only the `offline` category may back a release.
7. **Replay is mandatory.** `build_manifest()` re-executes the suite; a forged proof file cannot
   satisfy the rerun. `goe verify-release --proof <path>` replays anywhere.

## Evidence

| Item | Result |
|---|---|
| Offline suite | **201 passed, 0 skipped, 10 deselected** (network 9 + realdata 1) |
| Proof | `audit/test_evidence/20261114T191459Z_314ec188e2.proof.json` (schema v4) |
| Replay on the author machine | `goe verify-release` → accepted, rerun 201/201 |
| Replay on a fresh clone (6.9 MB, no venv, external interpreter) | accepted |
| Red-team round 1 (independent) | 4 attacks succeeded (2 × P0) → fixed, regression-tested |
| Red-team round 2 (independent, v3) | 4 × P1, 2 × P2 → fixed (pristine-tree execution, strict git, dirty verify, docs replay) |
| Red-team round 3 (independent, v4) | 1 × P1 (`export-ignore` filtered the tree) → fixed (worktree + blob verification) |
| Red-team round 4 (independent) | **PASS**, no P0/P1; 1 × P2 (`collect_ignore`) → fixed |
| Red-team round 5 (independent) | **PASS**, no P0/P1; 1 × P2 (`*_test.py` and single-item filtering) — the `*_test.py` half is fixed |

Write-ups: `audit/QA_REDTEAM_RELEASE.md` (rounds 1–3), this file (rounds 4–5).

## Verdict

**ENGINEERING: ACCEPTED WITH RESIDUALS** for the release gate.
P1-01 and P1-02 are fixed at the root, not patched per attack: the gate no longer trusts anything a
caller can write, and the evidence is reproducible from a clean clone.

**RESEARCH: NOT VALIDATED.** Unchanged by this work and independently audited in
`audit/RESEARCH_EVIDENCE_AUDIT.md`: the V2 candidates' competing hypotheses carry templated
`evidence_for` and identical `unknown` `evidence_against`, so the "distinguishing evidence" step
is nominal. Per the charter this is reported as `DISCOVERY VALUE: NOT VALIDATED`, not as a bug to
patch by retuning thresholds.

## Residual risks (documented, accepted)

| # | Risk | Why it stays |
|---|---|---|
| 1 | Test *quality* is not provable. A commit that weakens an assertion but keeps the count passes. | Needs review or test-hash allow-lists, not a runtime gate. |
| 2 | Host-level tampering (a plugin installed into site-packages, `PYTHONSTARTUP`, a modified interpreter) is outside the threat model. | The gate trusts the interpreter it is launched under; `-I` isolation is a future hardening. |
| 3 | Non-ASCII paths were previously mis-compared; `core.quotePath=false` fixes the known case, exotic filenames remain untested. | P3. |
| 4 | Two concurrent `run_test_proof` calls in the same second can overwrite the same evidence file. | P3; releases are serial by convention (`release_<commit>.json` already refuses duplicates). |
| 5 | Temporary `goe-junit-*` directories are not removed on success. | P3 disk hygiene. |
| 5b | A committed `conftest.py` can still drop a *single* item from a collected file, so a file with two tests can lose one and stay green. | Indistinguishable from committing a test deletion without a per-file baseline manifest; recorded as accepted P2. |
| 6 | Cross-OS replay (Linux) was not executed here; the proof is path-free and a fresh clone replays on macOS. | Needs a CI runner; no CI exists in this repository yet. |
| 7 | Stale `goe_clean*` worktrees from earlier sessions still exist in `.git/worktrees`. | Pre-existing; `git worktree prune` is safe but was not run without authorisation. |

## Next actions

1. Add a CI workflow (ubuntu-latest, Python 3.12) that runs `goe verify-release --proof <latest>`
   so cross-OS replay is tested on every push.
2. Decide the research-gate change: demote candidates with fewer than two hypotheses carrying
   discriminating (non-`unknown`) evidence to Market Intelligence.
3. Wire at least one missing series (same-day cross-asset returns / consensus revisions / OIS path)
   so the distinguishing-evidence step can actually run.
4. Prune stale worktrees and add cleanup for `goe-junit-*`.
