# Phase-1 User Guide — supervised research assistant

## 1. Check environment and data
```bash
.venv/bin/python -m goe.cli doctor --json
```
Normal: rc=0 and checks are `ok`/`warn`. Warnings about optional external providers are
not code failures. Data summary is in `data/goe.db`; the current observation cutoff is the
max price date (see `research status` / Finding `decision_as_of`).

## 2. Update market data (correct order)
```bash
.venv/bin/python -m goe.cli ingest --mode incremental
```
This is the supported update entry. It compares candidate/dependency price fingerprints
and queues related research updates automatically.
Then optionally:
```bash
.venv/bin/python -m goe.cli scan --as-of YYYY-MM-DD
```
Do **not** assume a scan alone re-activates research; use `ingest` first for that hook.

## 3. See candidates and research state
```bash
.venv/bin/python -m goe.cli research status
```
Shows workflow state, latest Finding, open/processed update counts. Candidate screening
fields are in the local DB; `evaluation/dossier` outputs are the readable research cards.

## 4. Run / resume research
```bash
.venv/bin/python -m goe.cli research next
# or a specific candidate
.venv/bin/python -m goe.cli research run --id <RESEARCH_ID>
```
Normal successful result: `finding=... status=INCONCLUSIVE` (or a documented status) and
an artifact under `research_results/<as-of>/<asset>/<finding_id>/`.

## 5. Review result and unknowns
```bash
.venv/bin/python -m goe.cli dossier \
  --artifact evaluation/v2_candidates_20_2026-11-13.json \
  --id <RESEARCH_ID> --out research_dossiers
```
Read `findings.md` / `finding.json`: facts, hypotheses, tests, supported/weakened/
insufficient, unknowns and next evidence. No trade/target/alpha claim is implied.

## 6. Updates, failures, retry, reopen
```bash
.venv/bin/python -m goe.cli research status
.venv/bin/python -m goe.cli research retry --id <RESEARCH_ID>
.venv/bin/python -m goe.cli research reopen --id <RESEARCH_ID> --reason "manual check"
.venv/bin/python -m goe.cli research next
```
- `PENDING/PROCESSING`: queued/working; `PROCESSED`: consumed; `FAILED`: needs retry.
- No-change reopen is consumed once; it does not loop.
- If a run fails, the finding history is preserved; retry resumes the update.

## 7. Stop
`Ctrl-C` the running CLI. There is no background daemon or auto-trading process.
No command merges main or deploys.

## 8. What is intentionally outside phase 1
Investment verdicts, position sizing, proof of Alpha or superiority over V1, full causal
identification, and unattended continuous operation are **not** phase-1 deliverables.
