"""Freeze/release manifest: pins code, config, data, scan and test evidence."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .db import Store


class ReleaseError(RuntimeError):
    pass


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return ""


def build_manifest(store: Store, *, out_dir: str | Path = "audit/releases",
                   test_count: int | None = None, notes: str = "",
                   require_clean: bool = True) -> dict[str, Any]:
    dirty = bool(_git("status", "--porcelain"))
    if require_clean and dirty:
        raise ReleaseError("refusing to freeze a dirty worktree; commit or set require_clean=False")
    if test_count is None:
        raise ReleaseError("test_count is required for a release freeze")
    scan = store.conn.execute(
        "SELECT scan_id,as_of,status,config_hash,data_hash,started_at FROM scan_runs "
        "ORDER BY started_at DESC LIMIT 1").fetchone()
    if not scan or scan["status"] != "success":
        raise ReleaseError("latest scan is missing or not successful; run a real scan first")
    counts = {"anomalies": store.scalar("SELECT COUNT(*) FROM anomalies") or 0,
              "opportunities": store.scalar("SELECT COUNT(*) FROM opportunities") or 0}
    by_status = {r[0]: r[1] for r in store.conn.execute(
        "SELECT status,COUNT(*) FROM opportunities GROUP BY status")}
    manifest = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "git_dirty": dirty,
        "scan": dict(scan) if scan else None,
        "scan_counts": counts, "opportunities_by_status": by_status,
        "test_count": int(test_count),
        "notes": notes,
        "artifacts": {},
    }
    import hashlib
    for p in [Path("reports") / f"report_{scan['as_of']}.md",
              Path("reports") / f"scan_{scan['as_of']}.json"]:
        if p.exists():
            manifest["artifacts"][str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    stamp = manifest["git_commit"][:10] or datetime.now(timezone.utc).strftime("%Y%m%d")
    path = out / f"release_{stamp}.json"
    if path.exists():
        raise ReleaseError(f"release manifest already exists: {path}")
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["path"] = str(path)
    return manifest
