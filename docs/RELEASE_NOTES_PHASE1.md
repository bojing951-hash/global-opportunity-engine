# Phase-1 release notes — research assistant candidate

## What it can do
- Monitor an existing multi-asset database and produce materiality/gap-qualified candidates.
- Lock a research event/decision as-of and generate a source-bound research spec.
- Run deterministic preliminary cross-asset tests and preserve versioned findings.
- Distinguish supported, weakened, insufficient and unknown hypotheses.
- Re-activate research after related asset/peer revisions, with idempotent notifications.
- Produce evidence-gated intelligence that explicitly refuses mispricing claims without
  a market-expectation baseline.

## Fixed in this cycle
- CLI regression in `doctor`, `events --check`, `replay`.
- Dependency-aware peer revisions (QQQ reactivates on IEF, etc.).
- PROCESSING crash/planner failure recovery.
- Repeated content transitions B→C→B→C use occurrence batches, not permanent hash dedupe.
- Cache-hit findings reapply current hypothesis state to the DB.

## Start
See `docs/USER_GUIDE_PHASE1.md`. Minimum: `doctor` → `ingest` → `research status` →
`research next` → `dossier`.

## Known limits
- Data ends 2026-11-13; no real post-cutoff observation. Continuous unattended operation
  is not validated.
- No user/expert triage scoring; TRIAGE VALUE NOT VALIDATED.
- No investment Alpha, trade direction, target price or causal proof.
- External provider credentials/network may be required for fresh ingestion.
- B deep-research capabilities remain external and were not modified.

## Versions
Candidate tag `phase1-research-assistant-rc.1`; exact commit and CI are in the final
delivery. This is not a final release until independent audit and user merge decision.
