# Research Mission 01 — QQQ relative underperformance, 2026-11-05

## Why this question
QQQ fell 6.49% while SPY fell 4.41% on 2026-11-05 (a 2.08 pp relative underperformance),
with VIX +69.66%. This is a material US cross-asset event with competing mechanisms.
Decision as-of: 2026-11-13. The event is locked in the persisted Event Contract
(`relative_strength_extreme / underperform / 2026-11-05`).

## Competing explanations
- H-RISK: risk-off/flight-to-quality. Prediction: SPY down and VIX up; duration/quality bid.
- H-RATE: rate/duration shock. Prediction: yields up (IEF down); QQQ underperforms.
- H-TECH: growth/tech-specific de-rating. Prediction: QQQ underperforms SPY; not separable
  from duration without sector/constituent data.
- H-DATA: index construction/data artifact.

## Actual evidence (GOE prices DB; same-day US closes)
| Series | 2026-11-05 |
|---|---:|
| QQQ | -6.49% |
| SPY | -4.41% |
| VIX | +69.66% |
| IEF | +0.34% |
| DXY | +0.04% |
| Gold | +0.99% |

Tests: historical percentile (0.40%, tail), relative underperformance (pass), risk-off
(SPY<0 & VIX>0, pass), rate-up shock (IEF<0, **fail**), classic dollar/gold safe-haven
(fail), 3-day reversal +4.28%.

## What was learned
- **Risk-off/flight-to-quality is supported** by the joint SPY/VIX/IEF pattern.
- **A simple yield-up shock is weakened/contradicted**: IEF rose, not fell.
- QQQ's relative underperformance is real and consistent with growth/duration de-rating,
  but this data cannot separate that mechanism from broad risk-off.
- No data-artifact flag is apparent, but this is not proof of clean index construction.

## Investment relevance
- The event is a risk/duration event, not evidence of a rate-driven tech de-rating.
- No implied-rate/options/consensus baseline is available, so:
  - `MARKET_EXPECTATIONS_NOT_ESTABLISHED`
  - `MISPRICING_NOT_ESTABLISHED`
- Monitoring: 2Y/10Y decomposition, sector breadth, post-event reversal, positioning.
- No trade direction, target price, or alpha claim.

## Information gain vs baseline
A simple price/anomaly screen only prioritizes “QQQ -6.49%”. GOE additionally:
1. rejects a simple rates-up explanation using IEF;
2. supports the risk-off channel with SPY/VIX;
3. flags the unresolved growth/duration attribution.
This is a real incremental research distinction, **not** proof of investment alpha.

## Limits / falsification
- One event; no intraday data; IEF is a duration proxy, not a yield decomposition.
- Falsified if later evidence shows yields rose sharply intraday or QQQ underperformance
  was driven by an identified idiosyncratic earnings event.
- DISCOVERY VALUE: NOT VALIDATED.
