# Research Discovery & Investment Intelligence — real-data results

## Discovery qualification (2026-11-13 queue)

`evaluation/discovery_cases.json`:

| Class | Count | Meaning |
|---|---:|---|
| RESEARCH_READY | 0 | no candidate has two measured discriminating evidence items yet |
| EVIDENCE_TO_COLLECT | 4 | N225/TAIEX/QQQ/XLV are worth research but evidence readiness is incomplete |
| INTELLIGENCE_ONLY | 16 | low explanatory gap or low decision relevance; retain as facts |
| DATA_ARTIFACT | 1 | 2026-04-30 CM_AGR_CT month-end continuous-futures case; verify raw roll metadata |

The correct result is **not** "20 opportunities". The strict evidence gate leaves zero
research-ready candidates. VIX is retained as intelligence only; CT is flagged as a likely
construction artifact, not an economic question.

## Investment intelligence

`evaluation/investment_intelligence.json` for the KOSPI V2 finding:

- `MARKET_EXPECTATIONS_NOT_ESTABLISHED` — no implied-rate/consensus/options distribution
  baseline in this run.
- `MISPRICING_NOT_ESTABLISHED` — price co-movement alone is not an expectation gap.
- Scenarios/falsification and monitoring triggers are recorded; no direction, target,
  trade, or alpha claim.

## A→B real handoff

`evaluation/a_to_b_validation.json`:

- Question: 美日10年期国债收益率差在 2026-11-12 是多少？
- B capability: `SUPPORTED`; execution `ok`; semantic `ok_valid`.
- B returned 63 evidence rows and an S8 grounded answer with UST/JGB facts.
- Snapshot `research_snapshot_20261112_v2`; Gate A DEGRADED; observation dates 2026-11-09/10.
- A did not modify B; B output was parsed by the read-only adapter.

## Continuous research

KOSPI V1 (CNY evidence) and V2 (USDKRW newly analyzed) coexist for the same locked
2026-10-15 event. Both remain INCONCLUSIVE; no material conclusion change. True
post-cutoff new observations are `OBJECTIVELY_BLOCKED` by data ending 2026-11-13.

## Value

No independent labels, blind evaluation, or genuinely future sample. Benchmark comparison
is descriptive only; `DISCOVERY VALUE: NOT VALIDATED`.
