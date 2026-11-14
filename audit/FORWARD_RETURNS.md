# FORWARD RETURNS — descriptive, not a backtest

Selection is point-in-time (PIT mapping produced by `goe.evaluation`). Forward returns use
only prices after each as-of date. No costs, no position sizing, no direction adjustment;
the engine is a research-priority tool, not a portfolio. Small n (12 objects/method).

| method | n | mean fwd 1m | mean fwd 3m | mean abs fwd 3m | material move rate | mean excess 3m vs SPY | beat SPY rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| A_price_move | 12 | -0.0318 | 0.0004 | 0.1431 | 0.5833 | -0.0652 | 0.25 |
| B_anomaly_score | 12 | 0.0351 | 0.0475 | 0.1082 | 0.5 | -0.0181 | 0.3333 |
| C_engine | 12 | 0.0266 | 0.0407 | 0.0733 | 0.3333 | -0.025 | 0.25 |

Per as-of date (mean forward 3m return):

| as_of | median abs 3m (universe) | A | B | C |
|---|---:|---:|---:|---:|
| 2022-10-31 | 0.1117 | -0.0921 | 0.1604 | 0.1114 |
| 2023-03-31 | 0.0469 | -0.0617 | 0.0208 | 0.0588 |
| 2024-09-30 | 0.056 | 0.0683 | -0.0847 | -0.0653 |
| 2025-06-30 | 0.0598 | 0.0873 | 0.0934 | 0.0577 |

Interpretation rules:
- `material_move_rate` measures whether the selected objects subsequently moved ≥1.5× the
  cross-sectional median |3m| move; it is an attention/activity check, not a profit claim.
- Positive/negative mean returns are descriptive; a single date or a few objects can dominate.
- This does not repair the missing human/forward validation of the research process; it adds
  one historical, falsifiable check and must be read with the blind LLM evaluation.
