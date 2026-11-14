# DETECTION CONTRACT

## Output row
`anomaly_id, date (observation), available_date, detector, family, entity_id, entity_kind,
asset_class, region, direction, window, measure, magnitude, score, percentile, evidence`.

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
