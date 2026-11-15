# CI replay workflow (added 2026-11-15)

File: `.github/workflows/verify-release.yml`

- Triggers: push to `architecture/research-v2`/`main`, pull requests, manual dispatch.
- Runner: `ubuntu-latest`, Python 3.12, `actions/checkout@v4` with `fetch-depth: 0`.
- Installs the package + pytest, selects the newest `audit/test_evidence/*.proof.json` and runs
  `python -m goe.cli verify-release --proof "$PROOF"`.

Local validation: YAML parses and the same command replays the current proof on macOS.
**Not yet executed on GitHub Actions** (no runner was triggered in this session); cross-OS
execution remains the residual risk unless the branch is pushed and the workflow runs.
