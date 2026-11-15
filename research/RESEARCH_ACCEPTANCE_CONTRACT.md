# Research Product Acceptance Contract

## Product outcome
Convert real market observations into checkable Research Dossiers that answer:
what happened, why it matters, what is unexplained, competing explanations, distinct
predictions, supporting/contradicting evidence, critical unknowns, acquisition plan,
falsification, worthiness, evidence readiness, cost, next action, B capability/status,
result/open questions, independent review status and source/version references.

## Frozen real scenarios (as_of 2026-11-13 unless stated)
| Case | Candidate | Expected status | What acceptance demonstrates |
|---|---|---|---|
| A — research-worthy | N225 `RC-20261113-JP_EQ_N225-455ff8e1a32f` | high worthiness / partial readiness / watch / B unsupported | important phenomenon, local fit, real gaps, no forced conclusion |
| B — no explanatory gap | VIX `RC-20261113-US_VOL_VIX-c1092d4e5bea` | low worthiness / archive / gap 0 | no explanatory gap remains; no causal/explanatory claim is invented |
| C — evidence gap | TAIEX/QQQ/XLV watch IDs | medium worthiness / missing or partial / watch | research value retained although evidence not ready |
| D — data artifact | `CASE-D-CM_AGR_CT-20260430` (2026-04-30) | low / archive / data artifact | continuous futures near month-end; no false economic explanation |

Dossiers: `research_dossiers/2026-11-13/` (A/C), `research_dossiers/2026-04-30/` (D),
VIX in `2026-11-13`. Index: `research_dossiers/README.md`.

## Evidence rules
- Facts need source + available_at; no synthetic market facts in production dossiers.
- Support and refutation are both recorded, but never double-count the same claim.
- R² is association, not causality or mispricing.
- Unknown data remains unknown; an acquisition plan is not evidence.
- B capability is checked; unsupported deep asset/sector/commodity tasks stay in A.
- `Independent Quality Review` is `NOT_INDEPENDENTLY_REVIEWED` unless a real reviewer ran.

## Current acceptance
- Engineering: PASS (241 proof, CI run 24/25 green; 50b60a1).
- Research workflow: **FUNCTIONAL** on real dossiers (A–D).
- Research value: **NOT VALIDATED** — no human/expert labels, no independent future window.
- A→B: **PARTIAL/NO-GO** — 0 handoff-eligible; B supports macro/rates/FX facts only.

## Non-goals
No price target, trade recommendation, mispricing conclusion, fabricated OIS/consensus, or
self-review presented as independent validation.
