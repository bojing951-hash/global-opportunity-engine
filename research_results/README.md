# Research execution results

| Case | Event | Result file | Finding |
|---|---|---|---|
| N225 2026-11-13 | 2026-11-06 | `2026-11-13/N225/findings.md` | Prior-US global selloff consistent (not same-day contradiction); Japan-local and regional-Asia co-move also supported; cannot separate them. Status `INCONCLUSIVE`, not alpha. Acceptance map: `ACCEPTANCE.md`. |

Reproduce: `python -m goe.cli research-case --case nikkei --as-of 2026-11-13`.
The finding stores source, event date, return inputs, test rules, hypothesis updates,
input SHA-256, code commit, missing data and `DISCOVERY VALUE: NOT VALIDATED`.
