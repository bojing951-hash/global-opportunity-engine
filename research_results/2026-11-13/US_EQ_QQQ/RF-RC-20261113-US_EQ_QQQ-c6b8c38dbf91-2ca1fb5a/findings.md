# Research Finding — US_EQ_QQQ 2026-11-13

- Event date: 2026-11-05
- Status: INCONCLUSIVE
- Input SHA256: `2ca1fb5ae9773e21bb5a3772b885704568258c92728b0911c8615d8ca90b4860`
- Code commit: `9c5636486fd4ef0c468e271d035feef0ee85ff8e`

## Acquired evidence
- QQQ relative_strength_extreme underperform on 2026-11-05: -6.49% vs SPY -4.41%; VIX +69.66%; decision as-of 2026-11-13.
- Source: GOE prices DB

## Tests
- **historical_percentile**: pass=True — two-sided 5% tail of the trailing 252-session return distribution
- **relative_underperform_test**: pass=True — event asset underperformed the US market
- **risk_test**: pass=True — risk-off: market down and VIX up
- **rate_test**: pass=False — rates-up shock would imply IEF down; positive IEF is flight-to-quality
- **dollar_test**: pass=False — classic safe-haven dollar/gold pattern is not required for a risk-off equity shock
- **reversal_test**: pass=True — post-event reversal through as-of

## Hypothesis updates
- **H-RISK**: SUPPORTED_BY_AVAILABLE_EVIDENCE — Risk-off co-movement is supported; not a causal proof.
- **H-RATE**: WEAKENED_BY_EVIDENCE — IEF up while QQQ underperformed is inconsistent with a simple yield-up shock; flight-to-quality.
- **H-TECH**: SUPPORTED_BY_AVAILABLE_EVIDENCE — Relative underperformance is observed; it is not separable from duration/risk-off.
- **H-DATA**: INSUFFICIENT_DATA — No index construction artifact indicated.

## What we learned
- US_EQ_QQQ 2026-11-05: -6.49% vs market -4.41%; spread -2.08%.
- VIX +69.66% and IEF +0.34%: risk-off/flight-to-quality is supported; a simple yield-up shock is not.
- DXY +0.04%, gold +0.99%; no classic safe-haven dollar/gold confirmation.
- Post-event 3-day return +4.28%.
- QQQ underperformance is consistent with growth/duration de-rating, but the mechanism remains unseparated.

## Still unknown
- intraday leadership/sector breadth
- implied rates and options distribution
- earnings revisions
- positioning

Retain in A; acquire the listed missing evidence. No B handoff for unsupported deep asset research.

DISCOVERY VALUE: NOT VALIDATED