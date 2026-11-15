# RESEARCH AUDIT — do V2 candidates carry distinguishing evidence?

- Date: 2026-11-15
- Scope: `research_v2_candidates` / `research_v2_hypotheses` as persisted in `data/goe.db`
  (latest scan `2026-11-13`, 20 candidates, 104 hypotheses)
- Method: read-only SQL; no re-scan, no rule tuning. This is a *method* audit, not a bug hunt.

## Verdict

**`DISCOVERY VALUE: NOT VALIDATED` — and the reason is structural, not statistical.**

The engine does generate competing explanations, but for the current data state the
*evidence that would distinguish them is `unknown` for almost every hypothesis*. The
candidate is still promoted to a research question, so the "distinguishing evidence"
step in the contract is nominal.

## Evidence

1. **Hypothesis identities are templates instantiated per asset.**
   104 hypothesis ids follow `<research_id>:H-<ASSET>-<TEMPLATE>` with 7 canonical templates
   (`LOCAL`, `GLOBAL`, `FUND`, `POLICY`, `FX`, `POS`, `ART`; sector/crypto variants add
   `SECTOR`/`STYLE`/`SUPPLY`/`DEMAND`/`CARRY`/`RISK`/`CRACK`/…). Template suffix counts:
   `POS` 16, `GLOBAL` 14, `ART` 14, `FUND` 10, `LOCAL` 7, `POLICY` 7, others ≤5.

2. **`evidence_against` is identical across unrelated assets.**
   - `RC-20261113-12:H-EQJP-GLOBAL` → `未提供同日跨资产横截面` / `no same-day cross-asset sample` / class `unknown`
   - `RC-20261113-13:H-EQMX-GLOBAL` → the same claim, the same value, the same class.
   The only per-asset variation is the observed 1-month return (9.7% vs 7.2%) in `evidence_for`.

3. **`evidence_for` is the observation, not evidence for the specific hypothesis.**
   For `GLOBAL`, `FUND`, `POLICY` and `POS` the "for" entry is
   `单月变动达到可检验幅度` with the same source (`prices`) — i.e. the anomaly itself.
   That cannot distinguish a global shock from a local one.

4. **Consequence for the contract.** The contract requires
   OBSERVED FACT → COMPETING EXPLANATIONS → *DISTINGUISHING EVIDENCE* → CRITICAL UNKNOWN →
   TESTABLE HYPOTHESIS → RESEARCH DECISION. With every discriminating test recorded as
   `unknown`, the fourth step cannot be met, yet candidates are still tiered `C` with
   `priority_rank` 6–12 rather than held as Market Intelligence.

## What this does *not* mean

- It is **not** fabricated evidence: the engine honestly labels the gaps as `unknown`
  (`一致预期/财报修正未接入`, `没有可核验的决议时点`, `未做汇率 beta`, …). That is the correct
  behaviour and should be preserved.
- It is **not** a claim that the anomalies are wrong. The descriptive layer (1,506 anomalies,
  transmission checks) is separate and unaffected.
- It is **not** a reason to retune thresholds against the same 7 historical cases. That would
  be the overfitting the charter forbids.

## Recommended gate change (not applied this round)

Demote a candidate to `intelligence` when fewer than two competing hypotheses carry at least
one *discriminating* evidence item (`class != "unknown"`), and record
`research_readiness: "evidence_gap"`. This turns "we cannot distinguish these explanations"
into an honest output instead of a research task.

Prerequisite: at least one of the missing series (cross-asset same-day returns / consensus
revisions / OIS path / CFTC positioning history) must be wired in, otherwise *every* candidate
demotes — which may well be the correct current answer, but should be a deliberate decision.

## Residual

- `research_tasks` has 2 rows; `research_v2_tasks` 1 row; no downstream result shows a
  hypothesis being rejected on evidence. Rejection is currently only visible for the 2
  `invalidated` candidates.
- The forward-return study (`audit/FORWARD_RETURNS.md`) measures price outcomes, not whether
  the *research question* was good. Selection quality and question quality remain unmeasured.


## Update 2026-11-15 (gate applied)
The recommended gate is now implemented. Cross-asset regressions supply measured discriminating
evidence; missing consensus/OIS feeds add nothing. Current real result: 20 candidates -> 1 research
(N225, evidence_ok), 19 intelligence (evidence_gap). No candidate is deleted or handed to B.
See `audit/EVIDENCE_GATE_DECISION.md`.
