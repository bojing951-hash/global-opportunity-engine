# Evaluation protocol v3 — separate the four questions

This protocol supersedes v2 for the **current** state. It deliberately does not change the
historical blind ratings or claim a new validation.

## Tracks (never collapsed into one score)
1. **Selection quality** — is the chosen asset/phenomenon material? Measured by the existing blind
   fact-card rating (A max move / B max anomaly / C V1 / D V2), if an independent rater exists.
2. **Question quality** — does the candidate contain >=2 competing hypotheses with distinct,
   observable predictions and tests? Measured structurally by
   `goe/research_quality.py` (type diversity, test availability), not by prose length.
3. **Evidence quality** — how many open hypotheses carry *measured* (not availability) discriminating
   evidence, and are claims duplicated across hypotheses? Measured by the same audit.
4. **Decision value** — could a resolved answer change a research/position decision? Descriptive flag
   from materiality x open gap x an available test; **not** an investment recommendation.

## Labels
There are no human/expert labels and no truly independent future window in this repository.
Therefore the only permitted discovery verdict is **DISCOVERY VALUE: NOT VALIDATED**.
A structural audit (tracks 2–4) can fail or pass descriptively; it cannot validate discovery value.

## Real current result
- 20 candidates -> 0 research / 20 intelligence. Mean measured evidence coverage 0.075.
- No candidate has two measured discriminating hypotheses. This is why no handoff is attempted.
- See `evaluation/RESEARCH_QUALITY_AUDIT.md`.

## Anti-overfitting rules
- Freeze the candidate set and code commit before any new rater.
- Do not change the gate or weights after seeing a new-window result.
- Report selection, question, evidence, decision separately; never synthesize a single "research
  score" or use return as a relevance label.
