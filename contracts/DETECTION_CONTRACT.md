# DETECTION CONTRACT

## Output row
`anomaly_id, date (detection/decision date), available_date, detector, family, entity_id,
entity_kind, asset_class, region, direction, window, measure, magnitude, score, percentile, evidence`.

For macro/valuation, `date` is the availability date (the date the engine may act on the value);
`available_date` is the same availability timestamp and `evidence.observation_date` is the original
reference period. This is intentional: recency/decision logic must never use an unpublished
observation date. For market prices `date` is the bar date and `available_date` is the completed-bar
availability date. The three fields must not be silently collapsed.

`evidence` MUST include: `threshold`, `formula`, `raw` values, `source` (source_id/tier/url if any),
`data_quality`, and for macro `observation_date`. Scores are normalized [0,1].

## Rules
- Detectors are trailing-window only; a detector must not read a row after its own date.
- A detector exception aborts the scan (pipeline checks `anomalies.attrs["errors"]`).
- Flood control/dedupe is deterministic; identical inputs produce identical anomaly ids.
- `available_date` is the date the observation could be known; opportunity/mechanism recency uses
  it with frequency-aware windows (daily 7d, weekly 21d, monthly 75d, quarterly 150d).
- An anomaly is NOT an opportunity. The detection layer may only output "what changed", never a
  mispricing or recommendation.

## Acceptance
Boundary test at window start (no fabricated trend flips), Monday/crypto weekend tests, deterministic
ids, evidence completeness, detector-failure rollback.
