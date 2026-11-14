# SCORING CONTRACT

## V1 (frozen baseline)
- 8 weights sum to 1.0; thresholds deep 0.68/watch 0.52/low 0.38; hard gates.
- V1 is preserved unchanged for comparison. No V2 work may overwrite V1 scores/artifacts.

## V2 (research triage)
- No arbitrary weighted score. Priority is a lexicographic rule with hard gates (see
  `RESEARCH_CONTRACT.md`).
- Every component used for ranking must be observable and recorded; missing data cannot increase
  priority. A candidate with no competing hypotheses / no falsification test is not a research
  candidate (market intelligence only).
- Evaluation must compare A (max move), B (max anomaly), C (V1 score), D (V2 triage) on identical
  dates/assets/data; development/validation/test splits must be recorded.
- If D fails to beat simple baselines, report NOT VALIDATED. Do not tune weights on test dates.
