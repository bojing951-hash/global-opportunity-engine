# Four P1 fixes — evidence (2026-11-16)

## F1 — CLI regression
- Removed ingest/update-notification code accidentally inserted into `doctor`, `events --check`, `replay`.
- Actual runs: `doctor --json` rc=0; `events --check --json` rc=0; `replay --start 2026-06-01 --end 2026-06-30 --step 21 --json` rc=0.
- External-provider warnings are separate from program errors.

## F2 — peer/dependency revisions
- `Store.research_dependencies` reads candidate asset + every peer in the latest Finding plan,
  plus the event contract asset.
- Fingerprints are computed per dependency **up to each research's as_of**.
- `goe ingest` compares before/after dependency snapshots and queues only related research.
- Integration test `test_ingest_peer_revision_reactivates_qqq`: changing only IEF through
  `cmd_ingest` queues an update for QQQ (SPY/VIX/IEF/DXY/gold dependency set).
- Unrelated asset changes produce no update; post-cutoff bars are excluded from fingerprints.

## F3 — PROCESSING crash recovery
- `pending_research_update` returns PENDING or stale PROCESSING; `retry` resets both
  FAILED and PROCESSING to PENDING.
- Planner and executor are both inside the guarded block; any exception marks the update
  FAILED and workflow BLOCKED.
- Test `test_planner_failure_does_not_leave_processing_stuck`: planner failure → FAILED,
  retry → PENDING, successful recovery → PROCESSED, no repeat.

## F4 — B→C→B transitions
- Trigger key now includes old and new content prefixes:
  `price:<instrument>:<old12>-><new12>`.
- A→B, B→C, C→B produce three distinct revisions; final B is processed.
- Re-selecting B reuses the historical B Finding if inputs equal; history is not overwritten.
- Test `test_b_to_c_to_b_transitions_are_not_swallowed` records three pending revisions.

## Boundary
- Ingest test uses a controlled provider with explicit dates; it is not a live cross-day run.
- No real post-cutoff market observations exist in the database.
