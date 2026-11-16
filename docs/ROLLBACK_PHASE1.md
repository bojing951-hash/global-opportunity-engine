# Rollback and data recovery — phase 1

## Code rollback
```bash
git fetch --tags origin
git checkout architecture/research-v2
git reset --hard <previous-known-good-commit>
```
Use `git revert <commit>` instead if the branch is shared. Do not force-push main.

## Database backup
Before a schema-affecting upgrade:
```bash
mkdir -p data/backups
sqlite3 data/goe.db ".backup 'data/backups/goe_phase1_YYYYMMDDTHHMMSSZ.db'"
```
Keep the backup in the runtime environment; it is not committed or uploaded.

## Recovery
1. Stop CLI processes.
2. Copy the backup to a temporary path and verify `PRAGMA integrity_check`.
3. Point the rollback code at that DB only after confirming the schema version.
4. Do not delete the existing DB; rename it aside if a swap is needed.
5. Research artifacts are versioned under `research_results/`; historical finding files
   must not be overwritten during rollback.

The current cycle has no destructive schema migration; the update-request table is additive.
