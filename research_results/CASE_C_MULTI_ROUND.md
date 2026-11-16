# Case C — KOSPI multi-round research (real data)

Same research ID, same locked event (`2026-10-15 drawdown_extreme/deep_drawdown`),
same decision as-of (2026-11-13). The second round newly analyzed an evidence series that
was stored but not used in round 1: **USDKRW**. This is `EXISTING_DATA_NEWLY_ANALYZED`,
not a newly acquired post-as-of observation.

| Round | Finding ID | FX evidence | Result |
|---|---|---|---|
| V1 | `RF-RC-20261113-KR_EQ_KOSPI-5710b185e99c-cc491d3f` | CNY (not the domestic FX pair) | INCONCLUSIVE; global lead only |
| V2 | `RF-RC-20261113-KR_EQ_KOSPI-5710b185e99c-d756fb85` | USDKRW +0.46% prior session | INCONCLUSIVE; global lead only; FX still too small |

## What changed
- V2's evidence input and hypothesis values changed; it has its own input hash and artifact dir.
- V1 directory was not overwritten; both are under `research_results/2026-11-13/KR_EQ_KOSPI/`.
- The event contract stayed `2026-10-15`; no event rebinding.
- The research decision is stored as `ACQUIRE_MORE_EVIDENCE`/`INCONCLUSIVE`, not a fabricated completion.

## Honest limitation
The database has no observations after the 2026-11-13 decision cutoff, so a genuinely
post-decision new observation cannot be used without lookahead. A true “new data arrives
later” Case C remains **OBJECTIVELY_BLOCKED** until a later vintage is ingested. The
mechanism for a new revision is implemented; this run demonstrates a new evidence channel,
not new post-cutoff information.
