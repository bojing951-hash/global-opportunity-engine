# Research gate decision — evidence sufficiency (2026-11-15)

Decision (user-approved): demote a candidate to Market Intelligence when fewer than two open
hypotheses carry at least one **measured, discriminating** evidence item. Availability notes,
price-move restatements and `unknown` gaps do not count.

Implementation:
- `goe/evidence/cross_asset.py` produces measured global/local/FX regression evidence.
- `goe/evidence/external.py` accepts PIT consensus and policy-curve files; missing files add nothing.
- `goe/research_triage.py` counts measured discriminator hypotheses; <2 -> `intelligence`,
  `research_readiness="evidence_gap"`; `research_readiness="evidence_ok"` otherwise.
- `goe/contracts.py` rejects a research-tier candidate without `evidence_ok` and >=2 such hypotheses.

Current real result (2026-11-13, 20 candidates):
- **1 research candidate: N225 (tier A, 2 measured hypotheses).**
- **19 intelligence** (evidence gap); they stay visible, are not deleted, and are not handed to B.
- Same-day cross-asset evidence is active; OIS is only a policy-path proxy; consensus remains
  BLOCKED (no licensed public history) and is not fabricated.

This is a deliberate reduction in output, not a failure to generate candidates.
