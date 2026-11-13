#!/usr/bin/env bash
# Fail if credentials, databases or private data would enter the repository.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
fail=0

echo "== tracked files that must never be committed =="
for pat in '\.db$' '\.db-wal$' '\.db-shm$' '^\.env$' '\.parquet$' '^data/' '^exports/ia_runs/'; do
  if git ls-files | grep -Eq "$pat"; then
    echo "FOUND tracked: $pat"; git ls-files | grep -E "$pat" | head -5; fail=1
  fi
done
[ "$fail" -eq 0 ] && echo "  none"

echo "== secret-like patterns in tracked files =="
if git grep -nIE '(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA|OPENSSH|EC) PRIVATE KEY-----|xox[baprs]-[A-Za-z0-9-]{10,})' -- . 2>/dev/null; then
  echo "  ^ suspicious strings found"; fail=1
else
  echo "  none"
fi

echo "== .env files present but ignored =="
find . -maxdepth 2 -name '.env' -not -path './.venv/*' -print 2>/dev/null || true

exit $fail
