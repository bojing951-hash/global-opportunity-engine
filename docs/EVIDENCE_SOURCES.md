# Missing evidence sources — integration status (2026-11-15)

| Source | Status | What is actually wired | Limitation |
|---|---|---|---|
| Same-day cross-asset returns | **ACTIVE (derived)** | `goe/evidence/cross_asset.py` regresses each candidate on a global equal-weight factor, local benchmark and local FX using only FeatureSet returns up to as_of; emits measured `statistical_association` evidence with R²/beta/residual-z and `discriminating=true`. | Derived from available prices; not a factor model with fundamental loadings. |
| Policy path / OIS | **PARTIAL** | `config/evidence_sources.yaml` accepts a vendor-capable `ois` CSV; `goe/evidence/external.py` enforces `available_at <= as_of` and curve slope; `scripts/fetch_external_evidence.py` fetches FRED SOFR/2Y/10Y as a **policy-path proxy**. | **Not term OIS.** No licensed OIS curve is available in this environment; the proxy is disabled by default and is not presented as OIS. |
| Consensus / earnings revisions | **BLOCKED (adapter only)** | `consensus` CSV adapter with strict PIT, stale and source checks; tests use an explicit fixture. | No free/public licensed historical consensus feed exists for this universe (indexes/ETFs). No values are fabricated; candidates remain `evidence_gap` until a licensed file is supplied. |

Enable a local file for a controlled run:
```yaml
consensus:
  enabled: true
  path: data/consensus_revisions.csv
ois:
  enabled: true
  path: data/policy_curve.csv
```
The file rates are not committed (`data/` is ignored), so a clone without them must remain `evidence_gap`.

## Research gate consequence
`goe/research_triage.py` now counts only **measured** discriminating evidence (class != unknown and
`discriminating=true`) per open hypothesis. A candidate with fewer than 2 such hypotheses is
demoted to `intelligence` with `research_readiness="evidence_gap"`. With the current data:
- 20 candidates -> **0 research candidates, 20 intelligence**.
- This is the intended honest result while the measured-evidence gate is in force. Cross-asset
  evidence is measured, but only one strong local fit exists; consensus and term OIS are not
  available, so the gate cannot promote a candidate today.
