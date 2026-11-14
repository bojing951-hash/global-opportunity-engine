# FEATURE CONTRACT

## Output
`FeatureSet.long` columns, exactly:
`entity_kind, entity_id, asset_class, region, feature, window, date, value`.

- `date` = feature observation date (for macro features: **availability date**, with the original
  observation date retained in anomaly evidence).
- Values are trailing-only: the row at date t is computed only from records available by t.
- Missing/undefined values are absent or NaN; they are never zero-filled or forward-filled.
- `FEATURE_VERSION` identifies semantics; it must be bumped when the meaning changes.
- `prices` is the cleaned wide panel used for context; `returns` are per-instrument simple returns
  over valid observations; `macro` is availability-indexed; `positioning` is publication-lagged.
- Crypto native features are on a 24/7 calendar and independently cleaned; equity features stay on
  business days. Window labels (`1m`, `252d`) must be read with their calendar (documented in meta).
- `feature_data_quality` (price issues) and `stale_macro_series` travel with the FeatureSet.

## Acceptance
1. Schema/version test.
2. PIT property: `build(t)` equals `build(T).slice_as_of(t)` for all rows <= t on the same data
   snapshot (documented exception: a corporate action on t itself is unknowable at t).
3. Monday/equity returns and MA200 not destroyed by crypto/FX rows.
4. Macro rows are availability-dated; no unpublished print is present.
5. Missing OI ⇒ `net_to_oi` unknown, never raw net contracts.
