# Research Finding — KR_EQ_KOSPI 2026-11-13

- Event date: 2026-10-15
- Status: INCONCLUSIVE
- Input SHA256: `3071aa83fcfa87622828d7ebeb4b1aa83e90fbe6327e33eeec56ab86f35ed3bd`
- Code commit: `2d03820f27d69846660e5fc6a121bd3316944492`

## Acquired evidence
- KOSPI 2026-10-15 near 5-year drawdown extreme; breadth/region/global explanations unresolved.
- Source: GOE prices DB

## Tests
- **historical_percentile**: pass=True — two-sided 5% tail of the trailing 252-session return distribution
- **local_asia_test**: pass=False — local co-move; association only
- **global_lead_test**: pass=True — prior US session selloff/VIX spike is consistent with a global lead
- **asia_regional_test**: pass=False — Regional peers did not both meet the pre-set threshold
- **fx_test**: pass=False — small FX move cannot explain the equity move
- **reversal_test**: pass=False — only bars after event through as-of

## Hypothesis updates
- **H-EQKR-LOCAL**: INCONCLUSIVE — Local peer did not meet its pre-set threshold; no local support.
- **H-EQKR-GLOBAL**: SUPPORTED_BY_AVAILABLE_EVIDENCE — Prior US selloff/VIX spike preceded Asia; same-date US close is not used.
- **H-EQ-FX**: WEAKENED_BY_EVIDENCE — Small FX move cannot explain the equity move by itself.
- **H-EQKR-POLICY**: INSUFFICIENT_DATA — No scheduled event in config/events.yaml; not proof no policy news.
- **H-EQKR-FUND**: INSUFFICIENT_DATA — No authorized consensus data; no fabrication.
- **H-EQ-REGIONAL**: INCONCLUSIVE — Regional co-move; sector/tech attribution unavailable.

## What we learned
- KR_EQ_KOSPI event 2026-10-15: -7.57%; local -1.03%.
- Prior US session 2026-10-14: -1.08%, -1.97%, +10.48%; global lead consistent.
- regional A -1.23%, regional B -4.90%; regional co-move did not meet threshold.
- CNY +0.00%; too small to be primary.
- Three-session reversal -0.03%.
- Neither local nor regional thresholds were met; only the global lead is supported.

## Still unknown
- local sector/constituent breadth
- regional supply-chain exposure
- consensus revisions
- event/news calendar

Retain in A; acquire the listed missing evidence. No B handoff for unsupported deep asset research.

DISCOVERY VALUE: NOT VALIDATED