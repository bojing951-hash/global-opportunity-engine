# New frozen-window evaluation (2025-12-31)

- 2025-12-31 was already used in a V1 validation case; it is **not independent** and is treated as exploratory only.
- Same universe/data/as-of for A max move, B max anomaly, C frozen V1, D V2 triage.
- 12 anonymised fact cards (3/method), independent LLM rater, 4 criteria 0–2.
- Single rater, no human labels; 2025-12-31 is not a future window and the rater may know outcomes.

| method | n | mean worthiness | P@3 | evidence suff. | falsifiability |
|---|---:|---:|---:|---:|---:|
| A max move | 3 | 1.083 | 0.00 | 1.33 | 1.00 |
| B max anomaly | 3 | 0.917 | 0.00 | 1.00 | 1.00 |
| C V1 score | 3 | **1.500** | **0.67** | 1.67 | 1.33 |
| D V2 triage | 3 | 1.000 | 0.00 | 1.00 | 1.00 |

**Result: D is not better than C/B/A; `DISCOVERY VALUE: NOT VALIDATED`.**
This run is on V2 snapshot 83a1160; later hypothesis refinements are not re-rated.
The new window does not rescue V2; no tuning on this window. It confirms that selection-level
worthiness is not established for V2. Research-question quality still lacks a clean independent
measure; a human/expert review is required.
