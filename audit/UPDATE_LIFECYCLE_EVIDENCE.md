# Update lifecycle evidence (V4.1)

| Scenario | Evidence | Type |
|---|---|---|
| A first research | QQQ canonical finding `...-e357c75d`; candidate screening high/partial/watch preserved | real historical data |
| B no change | `tests/test_research_orchestrator.py` no-change/consumption test; `next_case` returns None after processed | controlled |
| C manual reopen no change | reopen → next → run fake reuse → next None; old Finding `created_at` unchanged | controlled |
| D data revision | `tests/test_research_update_entry.py`: actual `cmd_ingest` entry, fake provider changes prices → pending `price_revision`; queue re-entry | controlled data revision |
| E same-second | reopen and next in same second without sleep; ledger consumes | controlled |
| F duplicate | same update key/fingerprint enqueues once; duplicate import idempotent | controlled |
| G update during run | update ledger leaves a second PENDING request after first PROCESSED; test coverage in orchestrator | controlled |
| H failure recovery | failed run marks update FAILED, workflow BLOCKED; retry resets PENDING, history intact | controlled |
| I queue continuation | high-priority unresolved candidate → WAITING, valid candidate selected | controlled |
| Real research | QQQ `2026-11-05`; risk supported, rate weakened, tech unresolved; investment intel gated | real historical data |

No claim of real cross-day ingestion or unattended operation: the database ends at
`2026-11-13`, and the ingest entry test uses a controlled provider mutation.
