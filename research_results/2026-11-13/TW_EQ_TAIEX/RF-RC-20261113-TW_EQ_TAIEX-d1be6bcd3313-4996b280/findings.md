# Research Finding — TW_EQ_TAIEX 2026-11-13

- Event date: 2026-11-06
- Status: INCONCLUSIVE
- Input SHA256: `4996b280f48613e9c724a3b3384c4cfe11a3830f87c2e755e0b8055ebc4b4183`
- Code commit: `77dd8686e01ebd37b1441012e8f1162a5aa9ef3c`

## Acquired evidence
- TAIEX 近期 price_return_shock（down，分数 0.81）；1 个月收益 -9.7%；回撤分位 0.20。
- Source: GOE prices DB

## Tests
- **historical_percentile**: pass=True — two-sided 5% tail of the trailing 252-session return distribution
- **local_asia_test**: pass=False — local co-move; association only
- **global_lead_test**: pass=True — prior US session selloff/VIX spike is consistent with a global lead
- **asia_regional_test**: pass=False — Regional peers did not both meet the pre-set threshold
- **fx_test**: pass=False — small FX move cannot explain the equity move
- **reversal_test**: pass=True — only bars after event through as-of

## Hypothesis updates
- **H-EQTW-LOCAL**: INCONCLUSIVE — Local peer did not meet its pre-set threshold; no local support.
- **H-EQTW-GLOBAL**: SUPPORTED_BY_AVAILABLE_EVIDENCE — Prior US selloff/VIX spike preceded Asia; same-date US close is not used.
- **H-EQ-FX**: WEAKENED_BY_EVIDENCE — Small FX move cannot explain the equity move by itself.
- **H-EQTW-POLICY**: INSUFFICIENT_DATA — No scheduled event in config/events.yaml; not proof no policy news.
- **H-EQTW-FUND**: INSUFFICIENT_DATA — No authorized consensus data; no fabrication.
- **H-EQ-REGIONAL**: INCONCLUSIVE — Regional co-move; sector/tech attribution unavailable.

## What we learned
- TW_EQ_TAIEX event 2026-11-06: -4.51%; local -1.27%.
- Prior US session 2026-11-05: -4.41%, -6.49%, +69.66%; global lead consistent.
- regional A -1.44%, regional B -5.96%; regional co-move did not meet threshold.
- CNY +0.04%; too small to be primary.
- Three-session reversal +11.47%.
- Neither local nor regional thresholds were met; only the global lead is supported.

## Still unknown
- local sector/constituent breadth
- regional supply-chain exposure
- consensus revisions
- event/news calendar

Retain in A; acquire the listed missing evidence. No B handoff for unsupported deep asset research.

DISCOVERY VALUE: NOT VALIDATED