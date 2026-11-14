# DATA CONTRACT

## Time semantics (single definitions; all modules MUST use these)
| Field | Definition | Example |
|---|---|---|
| `observation_time` | The reference period/date of the value (DB `date` for prices/indicators; bar date) | CPI reference month 2026-09-01 |
| `publication_time` | When the source first publishes the observation; may be unknown | CFTC Tuesday report |
| `available_at` | Earliest date the engine may use the value. Macro = observation + configured release lag; CFTC = report date + 4d; prices = bar date after completed-bar rule | CPI 2026-09-01 → 2026-10-16 |
| `ingested_at` | UTC timestamp the row was fetched (`fetched_at`); provenance only, never a decision time | 2026-11-13T15:05Z |
| `decision_as_of` | The research cutoff; no record with `available_at > decision_as_of` may enter features/detection/research | 2026-11-13 |

Rules:
1. Observation and availability are different columns/derivations. Never filter a release by its
   observation date to decide whether it was known.
2. A daily bar is complete only if captured after its own session close (DST-aware, +30 min), or
   captured on a later date (historical backfill). Crypto: only a later calendar date is complete.
   FX is 24h and exempt in the feature layer.
3. Calendars are asset-specific: equities use their exchange sessions; crypto is 24/7; FX is 24/5;
   cross-asset panels use business days and per-instrument valid-observation returns. No single
   calendar may silently drop weekend crypto or destroy Monday equity returns.
4. Corporate actions: split conversions adjust **post-action** observations back to the pre-action
   basis; pre-action history is immutable. Every action is recorded in `price_data_issues`.
5. Critical dependencies: global prices, UST curve (2Y+10Y mandatory), US_CPI, US_POLICY_RATE.
   Missing/stale critical data blocks a scan. Optional series (US_CAPE, EA_HICP, CFTC...) may
   degrade/disclose only. Per-market coverage collapse and per-curve-system staleness are critical.
6. Snapshot identity: every scan records `scan_id`, `config_hash` (all config files), `data_hash`
   (content hash of prices+indicators up to as_of), feature/detector versions. A frozen evaluation
   MUST pin all of these.
7. Data with `available_at > decision_as_of` is a P0 defect, not a warning.

## Failure behavior
- Provider empty/partial/crash → ingest status failed/partial; failed blocks; partial is disclosed
  with price/indicator coverage. No report may claim full coverage when ingest was partial.
- Detector exception → scan aborts and rolls back; never "success with a missing family".
- All writes for one scan are one SQLite transaction; artifacts are removed on failure.
