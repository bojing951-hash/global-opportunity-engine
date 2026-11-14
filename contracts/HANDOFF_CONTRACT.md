# A→B HANDOFF CONTRACT

## B's actual surface (local `investment-agent-dev`, verified)
`python3 ia_cli.py research-run --question "<text>" --out-dir <dir>`.
It runs an 11-step deterministic pipeline and writes `report.json`. Its zero-model intent gate:
- supports only a few factual query families (US/JP policy-rate level/differential, yields, USDJPY);
- rejects `out_of_scope` words (投资建议/仓位/买入/卖出/做多/做空/开仓/平仓/加仓/减仓/收益承诺...);
- unmatched asset-specific questions return `unmapped`/`no_registry_identity`.

## A obligations
- Send a self-contained, fact-only brief; remove OOS trigger words; never ask for advice/odds.
- Clear the run directory before each run; require report mtime > run start.
- `ok_valid` only if process status=ok, S8 `answered`, non-empty evidence_index, no failed step.
- `refused`/`unmapped`/`rejected`/timeout/missing/partial must be persisted as
  `not_completed:<semantic>`; never `completed`; CLI exit 2.
- Keep the candidate dossier in A even when B refuses; do not lose the research candidate.
- B's limitations are external; do not modify B's core logic.

## Acceptance
Fake-CLI matrix for all statuses; real-run refusal recorded; no path where rc!=0 or L2-only
artifact is completed; A→B end-to-end success is only claimed when a real S8 answered artifact
with evidence exists.
