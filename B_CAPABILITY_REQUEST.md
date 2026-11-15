# B capability request — Japan/Asia equity attribution

**For:** Claude Code / investment-agent maintainers  
**From:** GOE A research execution (DeepSeek Harness)  
**Do not modify B from A.** This is a request, not an implementation.

## Gap observed
For the 2026-11-06 N225 event (-5.96%), the PIT comparison is the PRIOR US session
2026-11-05: SPY -4.41%, QQQ -6.49%, VIX +69.66%, so a US-global lead is consistent.
The same-date 2026-11-06 US close is after Asia and must not be used. TOPIX -6.50%,
TAIEX -4.51% and KOSPI -6.02% co-moved; HSI/CSI were much smaller (-1.27%/-1.44%).
Broad indices cannot distinguish Japan-local from North Asia co-move, and do not identify
a technology-specific channel. B currently exposes macro/rates/FX facts, not deep equity/sector attribution.

## Requested capability
A factual, source-bound Japan equity sector/constituent attribution query for a frozen
date/window:
- TOPIX sector index returns and breadth on the event day and prior 5 sessions.
- Semiconductor/technology vs domestic-demand sector split, with observation dates.
- Optional: major constituent returns and weights (source/date/version), no price targets.
- Output must state missingness and must not infer causality or mispricing.

## Interface contract
- Input: `{economy: "JP", as_of: "YYYY-MM-DD", window: 5, sectors: true}`
- Output: `{supported: bool, as_of, source, observation_date, sectors: [{id,name,return,weight,
  available_at}], breadth, missing, warnings}`
- Errors: `UNSUPPORTED_CAPABILITY`, `INSUFFICIENT_DATA`, `STALE_DATA`; never a successful
  empty payload. `run_ok=false` must remain a refusal/error, not research completion.
- A will call it read-only and record source/available_at; A will not write B.

## Acceptance case
For 2026-11-06: report TOPIX sector breadth and a tech-vs-domestic split with source and
observation date; absent that, return `INSUFFICIENT_DATA` with what is missing.
