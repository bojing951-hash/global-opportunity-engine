#!/usr/bin/env bash
# Create (if needed) and push the private GitHub repository, then verify the
# remote HEAD matches the local commit.
#
# Requires one of:
#   - gh CLI authenticated (`gh auth login`), or
#   - GITHUB_TOKEN with repo scope (repo creation via API)
# SSH push access alone can only push to an ALREADY EXISTING repository.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

OWNER="${GOE_GITHUB_OWNER:-bojing951-hash}"
NAME="${GOE_GITHUB_REPO:-global-opportunity-engine}"
VISIBILITY="${GOE_GITHUB_VISIBILITY:-private}"
REMOTE="git@github.com:${OWNER}/${NAME}.git"

if git ls-remote "$REMOTE" >/dev/null 2>&1; then
  echo "remote exists: $REMOTE"
else
  echo "remote not found: $REMOTE — creating"
  if command -v gh >/dev/null 2>&1; then
    gh repo create "${OWNER}/${NAME}" --"${VISIBILITY}" --description \
      "Global investment opportunity discovery engine (upstream of investment-agent)"
  elif [ -n "${GITHUB_TOKEN:-}" ]; then
    curl -fsSL -X POST https://api.github.com/user/repos \
      -H "Authorization: Bearer ${GITHUB_TOKEN}" \
      -H "Accept: application/vnd.github+json" \
      -d "{\"name\":\"${NAME}\",\"private\":$([ "$VISIBILITY" = private ] && echo true || echo false),\"description\":\"Global investment opportunity discovery engine\"}" \
      >/dev/null
  else
    echo "ERROR: no gh CLI and no GITHUB_TOKEN; cannot create the repository." >&2
    echo "Create it manually: https://github.com/new (name: ${NAME}, private)" >&2
    exit 2
  fi
fi

git remote remove origin 2>/dev/null || true
git remote add origin "$REMOTE"
git push -u origin HEAD:main
LOCAL="$(git rev-parse HEAD)"
REMOTE_SHA="$(git ls-remote "$REMOTE" refs/heads/main | awk '{print $1}')"
echo "local=$LOCAL remote=$REMOTE_SHA"
[ "$LOCAL" = "$REMOTE_SHA" ] && echo "OK: remote matches local" || { echo "MISMATCH" >&2; exit 3; }
