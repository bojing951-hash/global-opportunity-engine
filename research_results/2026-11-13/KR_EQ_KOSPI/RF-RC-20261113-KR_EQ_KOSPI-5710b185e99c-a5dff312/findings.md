# Research Finding — KR_EQ_KOSPI 2026-11-13

- Event date: 2026-10-15
- Status: INCONCLUSIVE
- Input SHA256: `a5dff3120beb7dd05a3a03543fdf53cd293162e6ba17d92e3a3e413bc7be0a2b`
- Code commit: `2dbd52f89803b95831bee3912edd3d4e9da109e6`

## Acquired evidence
- KOSPI 2026-10-15 near 5-year drawdown extreme; breadth/region/global explanations unresolved.
- Source: GOE prices DB

## Tests
- **historical_percentile**: pass=True — two-sided 5% tail of the trailing 252-session return distribution
- **local_asia_test**: pass=False — HK/China co-move; association only
- **global_lead_test**: pass=True — prior US session selloff/VIX spike is consistent with a global lead
- **asia_regional_test**: pass=True — North Asia co-move supported; tech-specific attribution not identified
- **fx_test**: pass=False — small FX move cannot explain the equity move
- **reversal_test**: pass=False — only bars after event through as-of

## Hypothesis updates
- **H-EQKR-LOCAL**: INCONCLUSIVE — Broad co-move; not an independent instrument.
- **H-EQKR-GLOBAL**: SUPPORTED_BY_AVAILABLE_EVIDENCE — Prior US selloff/VIX spike preceded Asia; same-date US close is not used.
- **H-EQ-FX**: WEAKENED_BY_EVIDENCE — Small FX move cannot explain the equity move by itself.
- **H-EQKR-POLICY**: INSUFFICIENT_DATA — No scheduled event in config/events.yaml; not proof no policy news.
- **H-EQKR-FUND**: INSUFFICIENT_DATA — No authorized consensus data; no fabrication.
- **H-EQ-REGIONAL**: SUPPORTED_BY_AVAILABLE_EVIDENCE — Regional co-move; sector/tech attribution unavailable.

## What we learned
- KR_EQ_KOSPI event 2026-10-15: -7.57%; HK/China -1.03%.
- Prior US session 2026-10-14: -1.08%, -1.97%, +10.48%; global lead consistent.
- Japan -4.90%, Korea -7.57%; regional co-move supported.
- CNY +0.00%; too small to be primary.
- Three-session reversal -0.03%.
- Local and regional explanations both survive; broad indices cannot separate.

## Still unknown
- HK/China sector/constituent breadth
- regional supply-chain exposure
- consensus revisions
- event/news calendar

Retain in A; acquire the listed missing evidence. No B handoff for unsupported deep asset research.

DISCOVERY VALUE: NOT VALIDATED