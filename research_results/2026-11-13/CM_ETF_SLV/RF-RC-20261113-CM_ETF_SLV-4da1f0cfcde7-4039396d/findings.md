# Research Finding — CM_ETF_SLV 2026-11-13

- Event date: 2026-06-09
- Status: INCONCLUSIVE
- Input SHA256: `4039396dca75a789554f554fb9575084536b3a63c36f41b0d53a1037d0dc28c6`
- Code commit: `b93d5e66920ed95347568fe2e8c1f4c61570df84`

## Acquired evidence
- What explains the silver drawdown on 2026-06-09: dollar, real rates, risk-off, or data artifact?
- Source: GOE prices DB

## Tests
- **historical_percentile**: pass=False — two-sided 5% tail of the trailing 252-session return distribution
- **dollar_test**: pass=False — USD up with commodity down is consistent with dollar channel
- **real_rate_test**: pass=False — duration down (yields up) with commodity down is consistent with real-rate channel
- **risk_test**: pass=True — risk-off channel
- **gold_test**: pass=True — gold co-move checks a broad commodity/metal factor

## Hypothesis updates
- **H-CMD-DOLLAR**: INCONCLUSIVE — Dollar co-move is association; no causal identification.
- **H-CMD-REALRATE**: INCONCLUSIVE — IEF is a duration proxy, not a direct real-yield measure.
- **H-CMD-RISK**: SUPPORTED_BY_AVAILABLE_EVIDENCE — Risk channel is not separable from dollar/rates with these proxies.
- **H-CMD-SUPPLY**: INSUFFICIENT_DATA — No supply data; not fabricated.

## What we learned
- CM_ETF_SLV event 2026-06-09: -4.17%.
- DXY -0.14%, gold -1.76%, IEF +0.28%, SPY -0.29%, VIX +5.02%.
- Dollar/rate/risk channels overlap; none uniquely identified; supply data missing.

## Still unknown
- inventory/supply
- real yields
- positioning
- contract roll metadata

Retain in A; acquire the listed missing evidence. No B handoff for unsupported deep asset research.

DISCOVERY VALUE: NOT VALIDATED