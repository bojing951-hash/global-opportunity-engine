# Research Dossier RD-CASE-D-CM_AGR_CT-20260430

- Research ID: `CASE-D-CM_AGR_CT-20260430`
- Research Theme: `RT-DATA-ROLL-CM_AGR_CT`
- Decision as-of: `2026-04-30`
- Market / Assets: WORLD / CM_AGR_CT
- Case: CASE_D_DATA_ARTIFACT

## 1. Observed Facts

- **drawdown detector**: score 0.90; percentile 0.98 _(source: anomaly, available: 2026-04-30)_
- **continuous futures / month end**: True / True _(source: anomaly evidence, available: 2026-04-30)_

## 2. Why This Matters

- **materiality**: `{"importance": 0.2, "gap_score": 0.0, "near_month_end": true, "is_continuous_futures": true}`
- **decision_relevance**: `{"if_true": "No further research; mark data artifact.", "if_false": "Could investigate cotton fundamentals if raw data validates move."}`
- **observed_phenomenon**: Cotton continuous futures near 5y high at month-end (drawdown score 0.90; 5y percentile 0.98).

## 3. Research Question

What explains: Cotton continuous futures near 5y high at month-end (drawdown score 0.90; 5y percentile 0.98).

## 4. Competing Hypotheses

- **Continuous-futures roll / month-end data artifact**: If roll artifact, raw contract ratio/roll date explains the jump and no economic question remains.
- **Cotton supply/demand shock**: Cotton inventories/China demand should move before price; not available in current dataset.

## 5. Different Predictions

- If roll artifact, raw contract ratio/roll date explains the jump and no economic question remains.
- Cotton inventories/China demand should move before price; not available in current dataset.

## 6. Supporting Evidence

- **near month end on continuous futures**: 2026-04-30 _(source: anomaly evidence, available: 2026-04-30)_

## 7. Contradicting Evidence

- **no cotton inventory/China demand data**: unknown _(source: data_gap, available: 2026-04-30)_

## 8. Critical Unknowns

- raw cotton contract price and roll date
- CFTC cotton positioning
- USDA cotton inventory/China demand

## 9. Evidence Acquisition Plan

- 明确数据源、发布日期与可得时点：raw cotton contract price and roll date
- 明确数据源、发布日期与可得时点：CFTC cotton positioning
- 明确数据源、发布日期与可得时点：USDA cotton inventory/China demand

## 10. Falsification Conditions

- **compare raw front/next cotton contract around roll**: ratio jumps at roll
- **cotton inventory/China demand change**: supply/demand shock precedes price

## 11. Research Worthiness

- **rating**: low
- **rationale**: Case D: cotton continuous futures near month end; likely roll artifact, no economic research claim.

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
- **open_questions**: `["raw cotton contract price and roll date", "CFTC cotton positioning", "USDA cotton inventory/China demand"]`
- **learned**: No research result is claimed; unresolved unknowns remain explicit.

## 17. Independent Quality Review

- **status**: NOT_INDEPENDENTLY_REVIEWED
- **note**: No human/expert review was performed for this dossier. Do not treat the dossier as validated research value.

## 18. Source & Version References

- **artifact_path**: scripts/build_case_d_dossier.py
- **scan_id**: scan-20261115T044634Z-b68802
- **config_hash**: 7d4d8ae1a7ca110204f522359f57e8c627c89cdec753eea29b51af4a486fc187
- **data_hash**: 9350b109d05e0131412fc8631a6620eae73072ba17c208271b43b1d384c04054
- **theme_id**: RT-DATA-ROLL-CM_AGR_CT
- **evidence_count**: 2
- **source_note**: All evidence retains source and available_at; unavailable facts are unknown.

---
Content SHA-256: `09de4e8b905d148bda0d1636c6d8fce830b198d0b6477b1ee7002f0b4e0f177a`
DISCOVERY VALUE: NOT VALIDATED
