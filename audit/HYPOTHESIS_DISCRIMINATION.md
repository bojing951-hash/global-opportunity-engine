# Hypothesis discrimination — what the current V2 actually measures

## Framework
For each phenomenon the engine records:
- two or more competing hypotheses with **type**, **observable implications** and **tests**;
- `evidence_for` / `evidence_against` classified as observed fact, statistical association,
  causal hypothesis, unknown or judgement pending;
- measured cross-asset/local/FX regressions with R², beta and residual z, marked
  `discriminating=true` **only when the measurement is real** (FX requires R²>=0.30);
- a readiness gate: **>=2 open hypotheses with measured discriminating evidence** are required
  for a Research Candidate; otherwise the item is Market Intelligence (`evidence_gap`).

## What the framework refuses to do
- It does not treat "the price moved" as evidence for multiple hypotheses.
- It does not count an availability note, a missing-data gap, or a future data request as evidence.
- It does not convert a regression residual into a mispricing conclusion.
- It does not hand intelligence candidates to B.

## Current result (real 2026-11-13 artifact)
- 20 candidates, 0 research / 20 intelligence.
- Mean measured discriminating coverage 0.075; N225 has one strong local fit (R²~0.72) but not two.
- 0 duplicate evidence claims after the dynamic evidence gate.
- The absence is an **evidence limitation**, not a code failure: consensus and term-OIS feeds are not
  available (consensus BLOCKED, OIS policy proxy only), and cross-asset measurements explain the
  candidates but do not leave two competing open explanations.

## Consequence
This is an honest output under the approved gate. If the product requires research candidates every
week, either (a) wire a licensed consensus/term-OIS feed, or (b) explicitly lower the evidence gate
(with the understanding that cards become research questions with unmet evidence). Do not tune the
gate on the reused historical dates.
