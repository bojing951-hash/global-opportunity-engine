# Research closed-loop acceptance — N225 2026-11-13

| Contract | Evidence | Status |
|---|---|---|
| A Evidence acquisition | `evidence.json`: PIT-aligned same-day Asia returns and prior-US-session SPY/QQQ/VIX/USDJPY, source `GOE prices DB`, data dates; input SHA-256 in `finding.json` | PASS — new event cross-section was not in the candidate evidence record |
| B Actual test | `tests.json`: local, prior-US global lead, regional Asia, FX, reversal, with explicit thresholds | PASS |
| C Hypothesis update | `finding.json` + DB `research_v2_hypotheses`: H-GLOBAL and H-LOCAL/H-ASIA supported; H-FX weakened; policy/fundamental insufficient | PASS (evidence evaluation, not causal proof) |
| D Research finding | `findings.md`: N225 -5.96%, TOPIX -6.50%, prior US SPY -4.41/QQQ -6.49/VIX +69.66, regional Asia co-move, 3-day rebound +6.64%, unresolved local-vs-regional | PASS — `INCONCLUSIVE`, no alpha/mispricing claim |
| E Independent QA | `audit/QA_RESEARCH_EXECUTION_2.md` (after re-audit) | pending / see report |

## Key correction
The first execution compared N225's 2026-11-06 close with the **same-date** US close,
which occurs after Asia closes. That is lookahead. The corrected execution uses the
prior US session 2026-11-05: US-global risk is **consistent**, not contradicted.
The local and regional Asia explanations also survive; broad indices cannot separate them.

## Remaining unknowns / blockers
- TOPIX sector/constituent breadth; Asia semiconductor exposure.
- Consensus/earnings revisions (no licensed feed).
- Policy/news calendar coverage on 2026-11-06 (events.yaml has no scheduled event).
- B cannot perform deep Japan equity/sector attribution; capability request issued.

**DISCOVERY VALUE: NOT VALIDATED.**
