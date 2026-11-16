# Research Finding — US_EQ_QQQ 2026-11-13

- Event date: 2026-11-05
- Status: INCONCLUSIVE
- Input SHA256: `e96d847726e81d6f5d28390acb5a57ae9d7bb7ddc728da3d80dc100f5521525b`
- Code commit: `9c5636486fd4ef0c468e271d035feef0ee85ff8e`

## Acquired evidence
- QQQ relative_strength_extreme underperform on 2026-11-05: -6.49% vs SPY -4.41%; VIX +69.66%; decision as-of 2026-11-13.
- Source: GOE prices DB

## Tests
- **historical_percentile**: pass=True — two-sided 5% tail of the trailing 252-session return distribution
- **local_asia_test**: pass=None — local market co-move; association only
- **global_lead_test**: pass=None — prior US session selloff/VIX spike is consistent with a global lead
- **asia_regional_test**: pass=None — Regional peers did not both meet the pre-set threshold
- **fx_test**: pass=None — small FX move cannot explain the equity move
- **reversal_test**: pass=True — only bars after event through as-of

## Hypothesis updates
- **H-EQ-LOCAL**: INSUFFICIENT_DATA — Local peer did not meet its pre-set threshold; no local support.
- **H-EQ-GLOBAL**: INSUFFICIENT_DATA — Prior US selloff/VIX spike preceded Asia; same-date US close is not used.
- **H-EQ-FX**: INSUFFICIENT_DATA — Small FX move cannot explain the equity move by itself.
- **H-EQ-POLICY**: INSUFFICIENT_DATA — No scheduled event in config/events.yaml; not proof no policy news.
- **H-EQ-FUND**: INSUFFICIENT_DATA — No authorized consensus data; no fabrication.
- **H-EQ-REGIONAL**: INSUFFICIENT_DATA — Regional co-move; sector/tech attribution unavailable.

## What we learned
- US_EQ_QQQ event 2026-11-05: -6.49%; local market n/a.
- Prior US session 2026-11-04: n/a, n/a, n/a; global lead consistent.
- regional market A n/a, regional market B n/a; regional co-move did not meet threshold.
- FX n/a; too small to be primary.
- Three-session reversal +4.28%.
- Neither local nor regional thresholds were met; only the global lead is supported.

## Still unknown
- local market sector/constituent breadth
- regional supply-chain exposure
- consensus revisions
- event/news calendar

Retain in A; acquire the listed missing evidence. No B handoff for unsupported deep asset research.

DISCOVERY VALUE: NOT VALIDATED