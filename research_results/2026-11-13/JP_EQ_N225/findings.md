# Research Finding — JP_EQ_N225 2026-11-13

- Event date: 2026-11-06
- Status: INCONCLUSIVE
- Input SHA256: `d23f1f9969a0b4a2bdb507055208ee82a91fac33025ca83f9b47d4a0ff3c9826`
- Code commit: `ad203d97f36890a135ff1b60b945f38f11bc1c31`

## Acquired evidence
- What explains the N225 2026-11-06 selloff: Japan-local, regional North Asia, US/global, JPY, policy, or fundamentals?
- Source: GOE prices DB

## Tests
- **historical_percentile**: pass=True — two-sided 5% tail of the trailing 252-session return distribution
- **local_asia_test**: pass=True — TOPIX co-move supports broad Japan/local; association only
- **global_lead_test**: pass=True — prior US session selloff/VIX spike is consistent with a global lead
- **asia_regional_test**: pass=True — North Asia co-move supported; tech-specific attribution not identified
- **fx_test**: pass=False — small FX move cannot explain the equity move
- **reversal_test**: pass=True — only bars after event through as-of

## Hypothesis updates
- **H-EQJP-LOCAL**: SUPPORTED_BY_AVAILABLE_EVIDENCE — Broad co-move; not an independent instrument.
- **H-EQJP-GLOBAL**: SUPPORTED_BY_AVAILABLE_EVIDENCE — Prior US selloff/VIX spike preceded Asia; same-date US close is not used.
- **H-EQJP-FX**: WEAKENED_BY_EVIDENCE — Small FX move cannot explain the equity move by itself.
- **H-EQJP-POLICY**: INSUFFICIENT_DATA — No scheduled event in config/events.yaml; not proof no policy news.
- **H-EQJP-FUND**: INSUFFICIENT_DATA — No authorized consensus data; no fabrication.
- **H-EQJP-ASIA-REGIONAL**: SUPPORTED_BY_AVAILABLE_EVIDENCE — Regional co-move; sector/tech attribution unavailable.

## What we learned
- JP_EQ_N225 event 2026-11-06: -5.96%; TOPIX -6.50%.
- Prior US session 2026-11-05: SPY -4.41%, QQQ -6.49%, VIX +69.66%; global lead consistent.
- Taiwan -4.51%, Korea -6.02%; North Asia co-move supported.
- Prior USDJPY -0.07%; too small to be primary.
- Three-session reversal +6.64%.
- Local Japan and regional North Asia both survive; broad indices cannot separate.

## Still unknown
- TOPIX sector breadth
- Asia semiconductor exposure
- consensus revisions
- event/news calendar

Retain in A; acquire the listed missing evidence. No B handoff for unsupported deep asset research.

DISCOVERY VALUE: NOT VALIDATED