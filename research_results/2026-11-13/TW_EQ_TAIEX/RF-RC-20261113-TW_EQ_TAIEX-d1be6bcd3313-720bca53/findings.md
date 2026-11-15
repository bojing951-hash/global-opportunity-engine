# Research Finding — TW_EQ_TAIEX 2026-11-13

- Event date: 2026-11-06
- Status: INCONCLUSIVE
- Input SHA256: `720bca5385c22cac8800954d123e81f01ebd9425d68bad43374f1b114fde29c8`
- Code commit: `2dbd52f89803b95831bee3912edd3d4e9da109e6`

## Acquired evidence
- TAIEX 近期 price_return_shock（down，分数 0.81）；1 个月收益 -9.7%；回撤分位 0.20。
- Source: GOE prices DB

## Tests
- **historical_percentile**: pass=True — two-sided 5% tail of the trailing 252-session return distribution
- **local_asia_test**: pass=False — HK/China co-move; association only
- **global_lead_test**: pass=True — prior US session selloff/VIX spike is consistent with a global lead
- **asia_regional_test**: pass=True — North Asia co-move supported; tech-specific attribution not identified
- **fx_test**: pass=False — small FX move cannot explain the equity move
- **reversal_test**: pass=True — only bars after event through as-of

## Hypothesis updates
- **H-EQTW-LOCAL**: INCONCLUSIVE — Broad co-move; not an independent instrument.
- **H-EQTW-GLOBAL**: SUPPORTED_BY_AVAILABLE_EVIDENCE — Prior US selloff/VIX spike preceded Asia; same-date US close is not used.
- **H-EQ-FX**: WEAKENED_BY_EVIDENCE — Small FX move cannot explain the equity move by itself.
- **H-EQTW-POLICY**: INSUFFICIENT_DATA — No scheduled event in config/events.yaml; not proof no policy news.
- **H-EQTW-FUND**: INSUFFICIENT_DATA — No authorized consensus data; no fabrication.
- **H-EQ-REGIONAL**: SUPPORTED_BY_AVAILABLE_EVIDENCE — Regional co-move; sector/tech attribution unavailable.

## What we learned
- TW_EQ_TAIEX event 2026-11-06: -4.51%; HK/China -1.27%.
- Prior US session 2026-11-05: -4.41%, -6.49%, +69.66%; global lead consistent.
- Japan -5.96%, Korea -6.02%; regional co-move supported.
- CNY +0.04%; too small to be primary.
- Three-session reversal +11.47%.
- Local and regional explanations both survive; broad indices cannot separate.

## Still unknown
- HK/China sector/constituent breadth
- regional supply-chain exposure
- consensus revisions
- event/news calendar

Retain in A; acquire the listed missing evidence. No B handoff for unsupported deep asset research.

DISCOVERY VALUE: NOT VALIDATED