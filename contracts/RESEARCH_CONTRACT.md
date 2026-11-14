# RESEARCH CONTRACT (V2)

Every `ResearchCandidate` MUST contain:
- `research_id`, `as_of`, `market`, `asset_class`, `instruments`
- `observed_phenomenon` (facts + materiality)
- `competing_hypotheses`: at least 2, each with `id`, `label`, `type`
  (`risk_premium|fundamental|positioning_flow|global_risk|data_artifact|policy`), `implications`,
  `evidence_for`, `evidence_against`, `status` (`open|supported|contradicted|untestable`).
- `evidence`: each item classified as `observed_fact`, `statistical_association`, `causal_hypothesis`,
  `unknown`, or `judgement_pending`, with source and `available_at`. Unsupported claims are not
  allowed; no fact may lack provenance.
- `critical_unknowns`: what would change the conclusion, and whether it is obtainable.
- `falsification_conditions`: observable test/threshold/data, not prose.
- `required_data`, `research_cost` (hours, data access), `decision_impact` (if_true / if_false).
- `priority_tier` and `rationale`; `data_quality` and `evidence_gaps`.
- A/B/C/D evaluation IDs; V1 score may be attached for comparison but MUST NOT determine V2 tier.

## Priority rules (no arbitrary weights before validation)
Hard gates first:
1. Materiality: a genuine, important market change (not a near-high alone).
2. Explanatory gap: at least one competing hypothesis remains open and the standard drivers do not
   fully explain the move; otherwise the item is market intelligence, not a research question.
3. Distinguishability: there exists observable evidence that can separate at least two hypotheses.
4. Decision impact: the answer could plausibly change a position/hedge/research decision.
5. Cost: cheaper (available data, fewer hours) ranks higher among otherwise comparable items.

Within gates, ranking is lexicographic by (materiality, explanatory gap, distinguishability,
decision impact, inverse cost), not a hidden weighted sum. Equal items preserve stable tie-break by
research_id. V2 never claims mispricing; that is B's job.
