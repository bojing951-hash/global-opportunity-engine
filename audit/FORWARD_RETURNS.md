# FORWARD RETURNS — descriptive, not a backtest

Selection is point-in-time (PIT mapping produced by `goe.evaluation`). Forward returns use
only prices after each as-of date. No costs, no position sizing, no direction adjustment;
the engine is a research-priority tool, not a portfolio. Small n (12 objects/method).

| method | n | mean fwd 1m | mean fwd 3m | mean abs fwd 3m | material move rate | mean excess 3m vs SPY | beat SPY rate | mean excess 3m vs class | beat class rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A_price_move | 12 | -0.0318 | 0.0004 | 0.1431 | 0.5833 | -0.0652 | 0.25 | 0.0296 | 0.5 |
| B_anomaly_score | 12 | 0.0419 | 0.0509 | 0.0993 | 0.3333 | -0.0147 | 0.3333 | 0.0542 | 0.5833 |
| C_engine | 12 | 0.0492 | 0.0712 | 0.1039 | 0.3333 | 0.0056 | 0.25 | 0.0299 | 0.4167 |

Per as-of date (mean forward 3m return):

| as_of | median abs 3m (universe) | A | B | C |
|---|---:|---:|---:|---:|
| 2022-10-31 | 0.1117 | -0.0921 | 0.1129 | 0.2461 |
| 2023-03-31 | 0.0469 | -0.0617 | 0.0208 | 0.0588 |
| 2024-09-30 | 0.056 | 0.0683 | -0.0234 | -0.0653 |
| 2025-06-30 | 0.0598 | 0.0873 | 0.0934 | 0.0452 |

Interpretation rules:
- `material_move_rate` measures whether the selected objects subsequently moved ≥1.5× the
  cross-sectional median |3m| move; it is an attention/activity check, not a profit claim.
- Positive/negative mean returns are descriptive; a single date or a few objects can dominate.
- This does not repair the missing human/forward validation of the research process; it adds
  one historical, falsifiable check and must be read with the blind LLM evaluation.
