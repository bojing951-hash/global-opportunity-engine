# Research Finding — TW_EQ_TAIEX 2026-11-13

- Event date: 2026-07-31
- Status: INCONCLUSIVE
- Input SHA256: `8931e773d5bc2801302fba0909401349193a1cb8db4cd4457fbb6fdb308fdfb6`
- Code commit: `92df1b7dfc4c5292010296579d24a9262d8e9ea4`

## Acquired evidence
- TAIEX 近期 price_return_shock（down，分数 0.81）；1 个月收益 -9.7%；回撤分位 0.20。
- Source: GOE prices DB

## Tests
- **historical_percentile**: pass=True — two-sided 5% tail of the trailing 252-session return distribution
- **local_asia_test**: pass=False — TOPIX co-move supports broad Japan/local; association only
- **global_lead_test**: pass=False — prior US session selloff/VIX spike is consistent with a global lead
- **asia_regional_test**: pass=False — North Asia co-move supported; tech-specific attribution not identified
- **fx_test**: pass=False — small FX move cannot explain the equity move
- **reversal_test**: pass=True — only bars after event through as-of

## Hypothesis updates
- **H-EQTW-LOCAL**: INCONCLUSIVE — Broad co-move; not an independent instrument.
- **H-EQTW-GLOBAL**: WEAKENED_BY_EVIDENCE — Prior US selloff/VIX spike preceded Asia; same-date US close is not used.
- **H-EQ-FX**: WEAKENED_BY_EVIDENCE — Small FX move cannot explain the equity move by itself.
- **H-EQTW-POLICY**: INSUFFICIENT_DATA — No scheduled event in config/events.yaml; not proof no policy news.
- **H-EQTW-FUND**: INSUFFICIENT_DATA — No authorized consensus data; no fabrication.
- **H-EQ-REGIONAL**: INCONCLUSIVE — Regional co-move; sector/tech attribution unavailable.

## What we learned
- TW_EQ_TAIEX event 2026-07-31: +7.98%; HK/China +0.10%.
- Prior US session 2026-07-30: +1.68%, +3.30%, -17.28%; global lead consistent.
- Japan +4.03%, Korea +17.91%; regional co-move supported.
- CNY -0.07%; too small to be primary.
- Three-session reversal +3.46%.
- Local and regional explanations both survive; broad indices cannot separate.

## Still unknown
- TOPIX sector breadth
- Asia semiconductor exposure
- consensus revisions
- event/news calendar

Retain in A; acquire the listed missing evidence. No B handoff for unsupported deep asset research.

DISCOVERY VALUE: NOT VALIDATED