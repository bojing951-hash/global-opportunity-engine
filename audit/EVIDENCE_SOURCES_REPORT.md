# Evidence sources report (2026-11-15)

| Source | Delivered | Live/real? | Residual |
|---|---|---|---|
| Same-day cross-asset returns | `goe/evidence/cross_asset.py`: global factor, local benchmark, local FX regressions (R²/beta/residual z), labelled `statistical_association`, `discriminating=true`; only FeatureSet data up to as_of | **Yes, derived from real stored prices** | Factor is an equal-weight global basket, not a structural model |
| Policy path / OIS | `config/evidence_sources.yaml` + `goe/evidence/external.py`; `scripts/fetch_external_evidence.py` fetched FRED SOFR/2Y/10Y (30,961 rows) into an ignored local CSV | **Proxy only** | Not term OIS; requires a licensed OIS feed; disabled by default so a clone cannot silently use it |
| Consensus / revisions | File-backed PIT adapter, strict schema, staleness and `available_at` checks; test fixture | **No live data** | No public licensed historical consensus feed for indexes/ETFs; `BLOCKED` by external data access, not by code |
| Evidence gate | <2 open hypotheses with measured discriminating evidence -> `intelligence` + `evidence_gap`; contract enforces it | **Applied** | 20 candidates -> 0 research, 20 intelligence |

No synthetic values were inserted into production evidence. The local FRED proxy file is under
`data/` (ignored) and is not part of the release.
