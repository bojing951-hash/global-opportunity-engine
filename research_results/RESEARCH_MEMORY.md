# Persistent research memory contract

## Tables
- `research_v2_candidates`: immutable identity + current materialized snapshot.
- `research_v2_hypotheses`: current hypothesis state.
- `research_v2_hypothesis_revisions`: append-only revisions with status/source/hash.
- `research_v2_evidence`: append-only evidence records.
- `research_v2_events`: append-only workflow/hypothesis events.
- `research_v2_findings`: immutable findings (same finding_id never overwritten).
- `research_v2_workflow`: current workflow state projection.

## Rescan rule
`upsert_research_candidate` no longer deletes hypotheses or evidence. A scan may add new
hypotheses/evidence and append revisions, but cannot reset a research-updated status,
delete evidence, or overwrite a finding. New data creates a new finding id/hash.

## Acceptance tests
- `tests/test_research_identity.py::test_rescan_preserves_research_hypotheses_evidence_and_findings`
- `tests/test_research_orchestrator.py::test_orchestrator_runs_and_records_workflow`
- migration/append-only tables initialized by `Store`.
