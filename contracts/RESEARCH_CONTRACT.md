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

## Pre-registered ordinal gates (V2 implementation)
Materiality (M):
- M3: importance>=0.5 and (anomaly score>=0.90 or |1m|>=12% or drawdown percentile<=0.02)
- M2: importance>=0.5 and (score>=0.70 or |1m|>=5% or drawdown percentile<=0.05 or |vol z|>=2)
- M1: a real change (not near-high alone) or score>=0.70
- M0: near-high/trend alone, or importance<0.5 with no material change

Explanatory gap (G):
- G2: residual divergence component value>=0.30
- G1: residual>0 or a mechanism is mixed/unsupported/weak
- G0: no measurable gap and no conflicting mechanism

Distinguishability (D):
- D2: >=2 independent observable test families (residual, positioning, mechanism)
- D1: 1 family; D0: none

Decision impact (I):
- I2: importance>=0.8 and G>0
- I1: importance>=0.5; I0 otherwise

Tier:
- A: M3, G2, D2, I2
- B: M2, G>=1, D>=1
- C: M>=1, D>=1
- intelligence: otherwise (recorded, not ranked; never presented as an opportunity)

These are transparent rules, not weights. They are frozen before the assessment; changing them after
seeing evaluation results invalidates the claim.

## Research object data model (V2)
V2 MUST NOT reuse V1 `opportunities`/`opportunity_events`/`research_tasks` as its object store.
Tables (SQLite, foreign keys ON):
| Table | Key | References | Purpose |
|---|---|---|---|
| `research_v2_candidates` | `research_id` | — | immutable identity + current status/payload |
| `research_v2_hypotheses` | `hypothesis_id` | candidate CASCADE | >=1 per candidate; keyed by `research_id:hypothesis_key` |
| `research_v2_evidence` | `evidence_id` | candidate CASCADE, hypothesis nullable | facts/associations/unknowns with source & available_at |
| `research_v2_tasks` | `task_id` | candidate RESTRICT | A→B attempts; task survives candidate? candidate cannot be deleted while task exists |
| `research_v2_events` | auto | candidate CASCADE, task SET NULL | append-only status/handoff history |
| `research_v2_results` | auto | candidate/task RESTRICT | every A→B semantic result, success or failure |

Lifecycle: `active|intelligence` → `handoff_pending` → `handoff_failed` or `research_complete` → `archived`.
A failed handoff MUST leave the candidate and all hypotheses/evidence intact; it only updates status and
adds task/result/event. Candidate update never deletes old events. No RC-* row may live in V1 tables;
legacy RC-* rows are migrated once by `Store._migrate_legacy_v2()`.
`Store.research_integrity()` must return zero for all orphan counters and legacy RC rows.
