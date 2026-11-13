#!/usr/bin/env bash
# Daily incremental scan. Intended for cron/launchd; safe to run by hand.
#
#   07:30 local -> ingest (incremental) -> scan -> report + handoff files
#
# Exit codes: 0 success, 2 scan failed, 3 ingest-only failure.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${PY:-$REPO/.venv/bin/python}"
LOG_DIR="${GOE_LOG_DIR:-$REPO/logs}"
mkdir -p "$LOG_DIR"
STAMP="$(date +%Y%m%dT%H%M%S)"
LOG="$LOG_DIR/daily_${STAMP}.log"

{
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] goe daily scan starting"
  cd "$REPO" || exit 1
  "$PY" -m goe.cli scan --out "$REPO/reports"
  rc=$?
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] scan finished rc=$rc"
  # keep logs for 60 days
  find "$LOG_DIR" -name 'daily_*.log' -mtime +60 -delete 2>/dev/null || true
  exit $rc
} 2>&1 | tee -a "$LOG"

status=${PIPESTATUS[0]}
if [ "$status" -ne 0 ]; then
  echo "scan failed (rc=$status); see $LOG" >&2
  exit 2
fi
exit 0
