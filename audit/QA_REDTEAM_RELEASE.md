# INDEPENDENT QA — red team on the release gate (round 1)

- Auditor: independent red-team subagent (separate context, no access to the implementer's reasoning)
- Baseline: `b2cdbba` (186 offline tests); attacks replayed against `63e4afb` in a frozen clone
- Host: macOS, Python 3.12.13, `.venv`
- Rule: no writes to the audited tree; all experiments under `/tmp`

## Verdict

Round 1 **FAILED** the gate: a release manifest could be produced without running the
real suite. Four attacks succeeded. Round 2 (implementer) closed them; see the fix table.

## Confirmed findings

| ID | Severity | Attack | Reproduction result | Root cause |
|---|---|---|---|---|
| A1 | **P0** | Repository-root `pytest.py` shadows the real pytest (``python -m pytest`` puts cwd first on `sys.path`); the fake module prints `188 passed` and exits 0 | `run_test_proof` → 188 passed; `build_manifest` created a manifest | Gate trusted its own child process; no launcher isolation |
| A2 | **P0** | `tests/conftest.py` marks every test skipped, hidden from `git status` via `.git/info/exclude`; one real test passes | proof `passed=1, skipped=187, required=188` accepted locally; only a fresh clone failed | Skipped testcases counted as executed; no `passed == required` check; floor counted collected, not passed |
| A3 | **P1** | Proof lies about the console summary (`skipped=0`, log says `1 passed, 187 skipped`); rerun not compared on skipped | accepted | Counts parsed from free-text console output, first regex match, `tail` unused |
| A4 | **P1** | `core.worktree` / `GIT_DIR` points git at a decoy tree whose commit is clean | manifest recorded the decoy commit; the real failing tree was never tested | `_git_root` trusted git config/environment |
| A5 | **P2** | Absolute `junit_path` / `log_path` outside the repo | accepted on the author machine, fails after the directory moves | Evidence paths not constrained to the repository |
| — | **P1** | `git update-index --assume-unchanged` hides a modified conftest | proof accepted locally, clone rejected | `_dirty_code` only reads `git status` |
| — | **P2** | Nested-class / same-name JUnit `classname` mapping is ambiguous | observed only as false rejects; no false accept constructed | Classname resolver silently picked the longest file path |
| — | **P2** | `evaluation/` code may change after the proof | accepted (directory whitelisted) | `_check_commit` allow-list too wide |

## Fixes (v3 gate, commit `fe3867d`)

| Finding | Fix |
|---|---|
| A1 | Trusted launcher: `python -c "sys.path=[p for p in sys.path if p not in ('','.')]; import pytest; pytest.main(...)"`. A repo-root `pytest.py` can no longer win the import. Regression: `test_root_pytest_module_cannot_shadow_the_runner`. |
| A2 | JUnit `<skipped>/<failure>/<error>` testcases are rejected; `passed` must equal `required`; `skipped` must be 0; floor applied to the executed set. Regression: `test_skipped_tests_are_not_accepted`. |
| A3 | Counts come exclusively from JUnit `<testsuite>` attributes; console text is retained only as evidence. |
| A4 | `GIT_*` stripped for every git call; `_git_root` requires the reported root to contain the working directory. Regression: `test_core_worktree_decoy_is_rejected`. |
| A5 | Evidence paths must be repo-relative and resolve inside the root. Regression: `test_absolute_evidence_path_is_rejected`. |
| assume-unchanged | `git ls-files -v` flags `h`/`S`/`s` are treated as dirty. Regression: `test_assume_unchanged_is_treated_as_dirty`. |
| classname ambiguity | A JUnit testcase must resolve to **exactly one** collected node id; otherwise fail closed. |
| `evaluation/` | Removed from the post-proof change allow-list; `goe/ tests/ config/ contracts/ scripts/ pyproject.toml evaluation/` are all rejected after a proof. |

## Residual risks (documented, not fixed)

1. **Test quality is out of scope.** The gate proves *the tests present in the commit all ran*.
   It cannot prove the assertions are meaningful. A commit that weakens assertions and keeps the
   count passes. Mitigation requires review or test-hash allow-lists, not the gate.
2. **Ignored/ejected local files.** `_dirty_code` now rejects index flags, but files hidden by
   `.git/info/exclude` are still invisible to `git status`. The A2 attack no longer works because
   skipped tests are rejected, but a hidden conftest that rewrites assertions remains possible.
   Running the suite in a detached worktree from `HEAD` would remove the class; not implemented.
3. **Host-level tampering** (sitecustomize, installed pytest plugin, `PYTHONSTARTUP`) is outside
   the threat model; the gate trusts the interpreter it runs under.
4. `network`/`realdata` categories still carry placeholder floors (9/1) and are not release-eligible.

## Evidence

- Red-team transcript: `/tmp/rt/*` (ephemeral, not committed).
- Gate code: `goe/release.py` v3; tests: `tests/test_release_gate.py` (14 cases),
  `tests/test_contracts.py` release cases.
- Portable proof: `audit/test_evidence/*.proof.json`; replay with
  `python -m goe.cli verify-release --proof <path>`.

---

# Round 2 — red team on the v3 gate (2026-11-15)

- Baseline `047918f`; findings reproduced in `/tmp/rt3`; the audited tree was not modified.
- Verdict: **FAIL for local-tree attacks** (pure proof forgery was already closed).
- New: 4 × P1, 2 × P2, 3 × P3.

| ID | Sev | Attack | Root cause | Fix (v4) |
|---|---|---|---|---|
| B1 | **P1** | Host has an installed `goe` (`.pth`); a broken clone still got a manifest with `passed=198` | launcher appended the tree *after* site-packages, so `import goe` resolved to the installed copy | `import pytest` first, then `sys.path.insert(0, cwd)` |
| B2 | **P1** | corrupt index + modified test (`assert False`) + root conftest forcing pass → manifest, `git_dirty=false` | `_git()` returned `""` on failure, so a failed `git status` looked clean | strict `_git`; any git failure raises `ReleaseError` |
| B3 | **P1** | dirty worktree accepted by `verify-release` (rerun ran the edited test) | verify only checked commit ancestry | verify rejects a dirty worktree |
| B4 | **P1** | untracked root `conftest.py` hidden by `.git/info/exclude` forces a failing test to pass; rerun still accepted | execution used the working tree, which can contain files git cannot see | collect/run/replay in `git archive HEAD` (pristine tree) |
| B5 | **P1** | docs-only commit (`PROJECT_STATE.md`) made the current proof unreplayable | allow-list of post-proof paths did not include root project docs | root project docs allowed; code dirs still rejected |
| B6 | **P2** | `core.worktree` pointing at an ancestor tree: `_git_root(inner)` returned the outer root | only required root to *contain* cwd | release paths require `root == cwd` |
| B7 | **P2** | `PYTHONHOME` not cleared | `_clean_env` cleared `PYTHONPATH` only | `PYTHONHOME` cleared too |
| B8 | **P3** | non-integer JUnit attribute → `ValueError`; stderr swallowed on collection failure; `--no-rerun` accepts forged JUnit | robustness | `ReleaseError` with context; `--no-rerun` documented as structural-only |
| B9 | **P3** | nested `<testsuite>` could double-count | summed every nested element | counts from top-level testsuites only |

## Confirmed still fixed

- Round-1 A1 (root `pytest.py`) and A4 (`GIT_DIR`/`GIT_WORK_TREE`) no longer reproduce.
- assume-unchanged / skip-worktree are still rejected as dirty.
- Pure proof forgery (fake counts, duplicate/empty testcases, non-ancestor commits) does not pass.

## Residual

- `--no-rerun` is structural only and must not be used for release.
- Host-level tampering (a plugin installed into site-packages, `PYTHONSTARTUP`) remains outside
  the threat model; the gate trusts the interpreter it is launched with.
- Test *quality* (weakened assertions keeping the same count) is still not detectable.

## Round 3

Running against `6edc430` (v4). Outcome appended when complete.
