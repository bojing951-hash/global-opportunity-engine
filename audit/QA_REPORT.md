# QA REPORT — consolidated independent reviews

| Round | Reviewer / file | Verdict | P0/P1 found | Resolution |
|---|---|---|---|---|
| 1 | `FINAL_QA_AUDIT.md` | PASS WITH ISSUES | none unresolved | trend_break boundary fixed; docs aligned |
| 2 | `FINAL_QA_AUDIT.md` + `QA_ROUND2_FIX_VERIFICATION.md` | PASS WITH ISSUES | 2 P1: global stale-series deep cap; single-curve-system stale not critical | fixed; independent verification PASS |
| 3 data | `R3_DATA_AUDIT.md` | PASS WITH ISSUES | P1-A historical bars; P1-B contract gaps; crypto bad print bypass | fixed and re-tested |
| 3 research | `R3_RESEARCH_AUDIT.md` | FAIL (research) | policy narrative, invalidation, gap phase, validation weakness, handoff parser | fixed; blind result remains unfavourable |
| 3 red team | `R3_RED_TEAM_AUDIT.md` | NO-GO | P1-1 handoff false success; P1-2 partial provider; P1-3 readiness partial bar | fixed and re-verified |
| 3 engineering QA | `R3_FINAL_QA_ENGINEERING.md` | PASS WITH ISSUES | none | 157 offline tests, fault matrix passes |
| 3 final acceptance QA | `R3_FINAL_ACCEPTANCE_QA.md` then `R3_FINAL_ACCEPTANCE_QA2.md` | NO-GO → **PASS WITH ISSUES** | acceptance P1-R1/R2 (refused task not persisted; docs false success) | fixed; QA2 confirms closed |

## Current status
- Engineering: **ACCEPTED WITH ISSUES** (no P0/P1).
- Research capability: **NOT VALIDATED**. Round-3 blind evaluation ranks the engine below both
  simple anomaly and max-price-move rankings (1.188 vs 1.521 / 1.312); forward ex-top is +2.45% and
  class-relative hit rate is below the anomaly baseline. This is disclosed, not hidden.
- A→B: semantic failure correctly recorded (`not_completed:refused`, CLI exit 2); no real
  `ok_valid` deep-research artifact.
- Remaining P2/P3: future-split evaluation-day property edge; only first invalidation trigger;
  policy decision dates unknown (BIS availability); crypto/equity window labels; mechanism p-values
  approximate; multi-market holiday edge; docs historical snapshots retain old numbers.
