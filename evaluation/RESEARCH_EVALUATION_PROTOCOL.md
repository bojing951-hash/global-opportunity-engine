# RESEARCH EVALUATION PROTOCOL (pre-registered)

## Question
Does the V2 Research Discovery method (D) surface more valuable, falsifiable, decision-relevant
research questions than: A max |1m price move|, B max recent anomaly score, C V1 opportunity score?
It does not ask whether any method predicts returns; that is a separate, future test.

## Splits (must be fixed before running)
| Split | Dates | Use |
|---|---|---|
| Development | 2022-10-31, 2024-09-30 | V2 design/inspection; not evidence of out-of-sample value |
| Validation | 2023-03-31 | one comparison, no rule changes after seeing it |
| Test | 2021-12-31 | held out from V1/V2 design; used once for the final claim |

If any test date was used to change V2 rules, it is relabelled development and the claim becomes
NOT VALIDATED. No date may move from test to development after seeing results.

## Methods (identical universe/data/as-of)
- A: top-3 by |1m return|, theme-deduplicated.
- B: top-3 by strongest recent anomaly (availability-aware), theme-deduplicated.
- C: V1 `OpportunityEngine` top-3 (frozen V1 code; V1 score is attached only for comparison).
- D: V2 `goe.research_triage.build_candidates` top-3 researchable tiers (A/B/C), using the same
  FeatureSet/anomalies/mechanisms. D must never call V1 to rank.

## Blind cards
For every selected object, generate the SAME fact sheet (instrument/market/asset class, 1m/3m/12m
returns, volatility/drawdown/MA percentiles, CFTC positioning, recent anomalies, associated
mechanisms, data gaps). Method labels, V1 scores, V2 tier/rationale and hypotheses are NOT shown.
IDs are assigned after a global shuffle; mapping is stored separately.

## Raters
Independent LLM or human rater(s), given only cards and four criteria, 0–2:
1. real market change / materiality
2. research substance beyond price
3. falsifiability (can a specific test be formed?)
4. data sufficiency to start deep research
No post-as-of knowledge; no method inference. A human/expert panel is preferred; if unavailable,
state "single LLM rater, no human labels".

## Metrics
- Research Worthiness = mean of four criteria (0–2).
- Precision@3 = share of a method's 12 selected objects with mean ≥1.5.
- Relevant Research Recall = requires human relevance labels; if absent, report **NOT MEASURED**
  (do not substitute return or volatility as "relevance").
- Evidence Sufficiency = mean data_sufficiency.
- Falsifiability = mean falsifiability.
- Duplicate Rate = same theme repeated within a method.
- Unsupported Claim Rate = manual/LLM count of claims lacking source/evidence; report NOT MEASURED
  if not coded by an independent rater.
- Research Time Saved = requires human workflow measurement; NOT MEASURED unless timed.

## Decision rule
On the **test** split, D must beat both B and C on Research Worthiness and Precision@3, with no
material regression on evidence sufficiency/falsifiability. If D fails, publish:
`DISCOVERY VALUE: NOT VALIDATED`, keep A/B/C results, and do not tune weights on the test split.
Any improvement on development/validation only is reported as exploratory.

## Known limits
No human labels, single rater, small n, 4 selected/method/date, fact-card asymmetry (D selects
mechanism-rich assets), no cost/portfolio implication. These limits must appear with results.


## Known design limitations (after independent review)
- The common fact card measures **selection worthiness of an asset**, not the full V2 research
  question; V2's hypotheses/falsifiers are hidden for method-blindness. A future protocol should use
  a common research-brief template for all methods.
- D applies materiality/evidence gates before ranking; A/B/C do not. This can confound "selection
  filter" with "ranking"; the test split is therefore not proof of an isolated ranking effect.
- Test split (2021-12-31) yielded D n=1, below the pre-registered n>=3; result must be NOT VALIDATED.
- The 2026 LLM rater may know historical outcomes; no human/expert labels. These limits are not
  fixable by more tuning.
