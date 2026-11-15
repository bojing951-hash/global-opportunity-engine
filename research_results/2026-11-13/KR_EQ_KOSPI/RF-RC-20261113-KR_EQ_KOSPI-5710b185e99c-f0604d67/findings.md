# Research Finding — KR_EQ_KOSPI 2026-11-13

- Event date: 2026-06-17
- Status: INCONCLUSIVE
- Input SHA256: `f0604d67be5ba663a0a642e73cf3c1741d6885c576bf92673a2665d412c03589`
- Code commit: `d9f8c7dee874d523f7829da412deaccaec6e68c2`

## Acquired evidence
- KOSPI 2026-10-15 near 5-year drawdown extreme; breadth/region/global explanations unresolved.
- Source: GOE prices DB

## Tests
- **historical_percentile**: pass=False — two-sided 5% tail of the trailing 252-session return distribution
- **local_asia_test**: pass=False — local co-move; association only
- **global_lead_test**: pass=False — prior US session selloff/VIX spike is consistent with a global lead
- **asia_regional_test**: pass=False — Regional peers did not both meet the pre-set threshold
- **fx_test**: pass=False — small FX move cannot explain the equity move
- **reversal_test**: pass=True — only bars after event through as-of

## Hypothesis updates
- **H-EQKR-LOCAL**: INCONCLUSIVE — Local peer did not meet its pre-set threshold; no local support.
- **H-EQKR-GLOBAL**: WEAKENED_BY_EVIDENCE — Prior US selloff/VIX spike preceded Asia; same-date US close is not used.
- **H-EQ-FX**: WEAKENED_BY_EVIDENCE — Small FX move cannot explain the equity move by itself.
- **H-EQKR-POLICY**: INSUFFICIENT_DATA — No scheduled event in config/events.yaml; not proof no policy news.
- **H-EQKR-FUND**: INSUFFICIENT_DATA — No authorized consensus data; no fabrication.
- **H-EQ-REGIONAL**: INCONCLUSIVE — Regional co-move; sector/tech attribution unavailable.

## What we learned
- KR_EQ_KOSPI event 2026-06-17: +1.58%; local -0.74%.
- Prior US session 2026-06-16: -0.60%, -1.90%, +1.30%; global lead consistent.
- regional A +0.97%, regional B +0.72%; regional co-move did not meet threshold.
- CNY -0.13%; too small to be primary.
- Three-session reversal +2.82%.
- Neither local nor regional thresholds were met; only the global lead is supported.

## Still unknown
- local sector/constituent breadth
- regional supply-chain exposure
- consensus revisions
- event/news calendar

Retain in A; acquire the listed missing evidence. No B handoff for unsupported deep asset research.

DISCOVERY VALUE: NOT VALIDATED