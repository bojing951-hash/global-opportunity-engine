#!/usr/bin/env bash
# Install a launchd job (macOS) that runs scripts/run_daily.sh every day at 07:30
# local time. Optional: set GOE_SCHEDULE_HOUR / GOE_SCHEDULE_MINUTE.
#
# This script writes to ~/Library/LaunchAgents, which is outside the project
# directory. Review it before running; `--uninstall` removes the job.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.goe.daily"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
HOUR="${GOE_SCHEDULE_HOUR:-7}"
MINUTE="${GOE_SCHEDULE_MINUTE:-30}"

if [ "${1:-}" = "--uninstall" ]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "removed $PLIST"
  exit 0
fi

if [ ! -x "$REPO/.venv/bin/python" ]; then
  echo "error: $REPO/.venv/bin/python not found; run 'make setup' first" >&2
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${REPO}/scripts/run_daily.sh</string>
  </array>
  <key>WorkingDirectory</key><string>${REPO}</string>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>${HOUR}</integer><key>Minute</key><integer>${MINUTE}</integer></dict>
  <key>StandardOutPath</key><string>${REPO}/logs/launchd.out.log</string>
  <key>StandardErrorPath</key><string>${REPO}/logs/launchd.err.log</string>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
PLISTEOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "installed $PLIST (daily ${HOUR}:$(printf '%02d' "$MINUTE")); check with: launchctl list | grep ${LABEL}"
echo "uninstall with: $0 --uninstall"
