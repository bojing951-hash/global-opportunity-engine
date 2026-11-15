# Research Finding — US_FX_DXY 2026-11-13

- Event date: 2026-11-11
- Status: INCONCLUSIVE
- Input SHA256: `0358808361e407405278506c4297ecf33191f9e206fd3888b3370daa151533b5`
- Code commit: `b93d5e66920ed95347568fe2e8c1f4c61570df84`

## Acquired evidence
- What explains the US dollar index near its 5y high on 2026-11-11: rate differential, risk-off, broad USD, or data artifact?
- Source: GOE prices DB

## Tests
- **historical_percentile**: pass=True — two-sided 5% tail of the trailing 252-session return distribution
- **broad_usd_test**: pass=True — EUR lower and USDJPY higher confirms broad USD strength
- **rate_test**: pass=True — US duration down (yields up) alongside USD up is consistent with rate differential
- **risk_test**: pass=False — risk-off / safe-haven bid

## Hypothesis updates
- **H-FX-RATES**: SUPPORTED_BY_AVAILABLE_EVIDENCE — Duration down + USD up is consistent with yield support; association only.
- **H-FX-RISK**: WEAKENED_BY_EVIDENCE — Risk-off bid is a competing channel; cannot establish causality.
- **H-FX-BROAD**: SUPPORTED_BY_AVAILABLE_EVIDENCE — Cross-rate confirmation; no claim about equilibrium.
- **H-FX-DATA**: INSUFFICIENT_DATA — Index data are not a futures roll; artifact not indicated but not fully ruled out.

## What we learned
- US_FX_DXY event 2026-11-11: +0.67%.
- EURUSD -0.48%, USDJPY +0.46%, IEF -0.08%, SPY +1.32%, VIX -10.12%.
- Rate/broad-USD co-move is supported; risk-off is weakened at this event; no causal identification.

## Still unknown
- 2Y/10Y yield decomposition
- positioning
- policy calendar
- real-time news

Retain in A; acquire the listed missing evidence. No B handoff for unsupported deep asset research.

DISCOVERY VALUE: NOT VALIDATED