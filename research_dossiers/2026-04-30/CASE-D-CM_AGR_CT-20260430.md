# Research Dossier RD-CASE-D-CM_AGR_CT-20260430

- Research ID: `CASE-D-CM_AGR_CT-20260430`
- Research Theme: `RT-DATA-ROLL-CM_AGR_CT`
- Decision as-of: `2026-04-30`
- Market / Assets: WORLD / CM_AGR_CT
- Case: CASE_D_DATA_ARTIFACT

## 1. Observed Facts

- **drawdown detector**: near_high 0.90 _(source: anomaly)_
- **continuous futures / month end**: True / True _(source: anomaly evidence)_

## 2. Why This Matters

- **materiality**: `{"importance": 0.2, "gap_score": 0.0, "near_month_end": true, "is_continuous_futures": true}`
- **decision_relevance**: `{"if_true": "No further research; mark data artifact.", "if_false": "Could investigate cattle fundamentals if raw data validates move."}`
- **observed_phenomenon**: Live Cattle continuous futures near 5y high at month-end (drawdown percentile 0.98).

## 3. Research Question

What explains: Live Cattle continuous futures near 5y high at month-end (drawdown percentile 0.98).

## 4. Competing Hypotheses

- **Continuous-futures roll / month-end data artifact**: If roll artifact, raw contract ratio/roll date explains the jump and no economic question remains.
- **Cattle supply/demand shock**: Inventories/slaughter data should move before price; not available in current dataset.

## 5. Different Predictions

- If roll artifact, raw contract ratio/roll date explains the jump and no economic question remains.
- Inventories/slaughter data should move before price; not available in current dataset.

## 6. Supporting Evidence

- **near month end on continuous futures**: 2026-04-30 _(source: anomaly evidence)_

## 7. Contradicting Evidence

- **roll metadata unavailable**: unknown _(source: provider)_
- **no inventory/slaughter data**: unknown _(source: data_gap)_

## 8. Critical Unknowns

- raw contract price and roll date
- CFTC cattle positioning
- slaughter/inventory data

## 9. Evidence Acquisition Plan

- 明确数据源、发布日期与可得时点：raw contract price and roll date
- 明确数据源、发布日期与可得时点：CFTC cattle positioning
- 明确数据源、发布日期与可得时点：slaughter/inventory data

## 10. Falsification Conditions

- **compare raw front/next contract around roll**: ratio jumps at roll
- **inventory/slaughter change**: supply shock precedes price

## 11. Research Worthiness

- **rating**: low
- **rationale**: Case D: continuous futures near month end; likely roll artifact, no economic research claim.

## 12. Evidence Readiness

- **rating**: partial
- **research_readiness**: evidence_gap
- **measured_note**: Only measured, discriminating evidence counts; availability notes do not.

## 13. Research Cost

- **hours**: 3
- **data_access**: low

## 14. Next Research Action

No further research allocation; retain as market intelligence

## 15. B Capability / Handoff

- **supported**: False
- **kind**: deep_asset_research_unsupported
- **reason**: B is a macro fact workbench, not a general equity/sector/commodity valuation or mispricing engine; keep in A
- **eligibility**: a_retained
- **research_queue**: archive
- **tier**: intelligence

## 16. Result / Open Questions

- **result**: NOT_EXECUTED
- **open_questions**: `["raw contract price and roll date", "CFTC cattle positioning", "slaughter/inventory data"]`
- **learned**: No research result is claimed; unresolved unknowns remain explicit.

## 17. Independent Quality Review

- **status**: NOT_INDEPENDENTLY_REVIEWED
- **note**: No human/expert review was performed for this dossier. Do not treat the dossier as validated research value.

## 18. Source & Version References

- **artifact_path**: data/goe.db#anomalies/AN-ef670579d660c2
- **scan_id**: None
- **config_hash**: None
- **data_hash**: None
- **theme_id**: RT-DATA-ROLL-CM_AGR_CT
- **evidence_count**: 2
- **source_note**: All evidence retains source and available_at; unavailable facts are unknown.

---
Content SHA-256: `36d09a6284dd3bd631019906651c70d75fb00726d0d52c32907654a437256206`
DISCOVERY VALUE: NOT VALIDATED
