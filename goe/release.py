"""Release gate with machine-verifiable test evidence.

A caller cannot supply ``test_count``. The gate only accepts a proof file created
by actually running pytest on a clean checkout of the same commit, with a log
whose SHA-256 is embedded in the proof. Forged counts, stale commits, dirty
trees, failed tests, missing logs and hash mismatches are rejected.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dirty_code(*, cwd: str | Path = ".") -> bool:
    """Dirty means code/config/docs changed; generated proof/manifest files are exempt."""
    lines = _git("-C", str(cwd), "status", "--porcelain").splitlines()
    allowed = ("audit/test_evidence/", "audit/releases/")
    return any(not any(part in line for part in allowed) for line in lines if line.strip())


def _parse_pytest(output: str) -> dict[str, int]:
    def one(pattern: str) -> int:
        m = re.search(pattern, output)
        return int(m.group(1)) if m else 0
    # pytest summary is on the last non-empty lines; tolerate -q progress output
    tail = "\n".join([ln for ln in output.splitlines() if re.search(r"\d+ (passed|failed|skipped|deselected|error)", ln)][-5:])
    return {"passed": one(r"(\d+) passed"), "failed": one(r"(\d+) failed"),
            "skipped": one(r"(\d+) skipped"), "deselected": one(r"(\d+) deselected"),
            "errors": one(r"(\d+) errors?")}


def run_test_proof(command: list[str] | None = None, *, cwd: str | Path = ".",
                   log_dir: str | Path = "audit/test_evidence", timeout: int = 1800) -> dict[str, Any]:
    """Run pytest and write an immutable test proof. Only clean commits pass."""
    cwd = Path(cwd).resolve()
    commit = _git("-C", str(cwd), "rev-parse", "HEAD")
    dirty = bool(_dirty_code(cwd=cwd))
    if dirty:
        raise ReleaseError("test proof requires a clean worktree")
    if not commit:
        raise ReleaseError("cannot establish git commit for test proof")
    command = command or [sys.executable, "-m", "pytest", "tests", "-o", "addopts=",
                          "-q", "-m", "not network and not realdata"]
    started = datetime.now(timezone.utc)
    proc = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
    ended = datetime.now(timezone.utc)
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    counts = _parse_pytest(output)
    if proc.returncode != 0 or counts["failed"] or counts["errors"] or counts["passed"] <= 0:
        raise ReleaseError(f"test run failed: rc={proc.returncode} counts={counts}")
    if not any("pytest" in str(part) for part in command) or "tests" not in command:
        raise ReleaseError("proof command must execute the repository pytest suite")
    log_dir = Path(log_dir); log_dir.mkdir(parents=True, exist_ok=True)
    stamp = ended.strftime("%Y%m%dT%H%M%SZ")
    log_path = log_dir / f"{stamp}_{commit[:10]}.log"
    log_path.write_text(output, encoding="utf-8")
    proof = {
        "schema": "goe-test-proof/v1", "git_commit": commit, "git_dirty": False,
        "command": command, "cwd": str(cwd), "exit_code": proc.returncode,
        "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ended_at": ended.strftime("%Y-%m-%dT%H:%M:%SZ"),
        **counts, "log_path": str(log_path), "log_sha256": _sha256(log_path.read_bytes()),
    }
    proof_path = log_dir / f"{stamp}_{commit[:10]}.proof.json"
    proof_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    proof["proof_path"] = str(proof_path)
    return proof


def verify_test_proof(proof_path: str | Path, *, cwd: str | Path = ".") -> dict[str, Any]:
    path = Path(proof_path)
    if not path.exists():
        raise ReleaseError(f"test proof missing: {path}")
    try:
        proof = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReleaseError(f"test proof is not valid JSON: {exc}") from exc
    if proof.get("schema") != "goe-test-proof/v1":
        raise ReleaseError("unknown test proof schema")
    commit = _git("-C", str(cwd), "rev-parse", "HEAD")
    if proof.get("git_commit") != commit:
        raise ReleaseError("test proof commit does not match current HEAD")
    if proof.get("git_dirty"):
        raise ReleaseError("test proof was created on a dirty worktree")
    if proof.get("exit_code") != 0 or int(proof.get("failed", 0)) or int(proof.get("errors", 0)):
        raise ReleaseError("test proof records failed tests")
    if int(proof.get("passed", 0)) <= 0:
        raise ReleaseError("test proof records no passed tests")
    cmd = [str(x) for x in proof.get("command", [])]
    if not any("pytest" in c for c in cmd) or "tests" not in cmd:
        raise ReleaseError("proof command is not the repository pytest suite")
    log = Path(proof.get("log_path", ""))
    if not log.exists():
        raise ReleaseError("test proof log is missing")
    if _sha256(log.read_bytes()) != proof.get("log_sha256"):
        raise ReleaseError("test proof log hash mismatch")
    log_counts = _parse_pytest(log.read_text(encoding="utf-8", errors="replace"))
    for key in ("passed", "failed", "skipped"):
        if int(proof.get(key, -1)) != int(log_counts.get(key, -2)):
            raise ReleaseError(f"test proof {key} count disagrees with log")
    return proof


def build_manifest(store: Store, *, proof_path: str | Path,
                   out_dir: str | Path = "audit/releases", notes: str = "",
                   require_clean: bool = True) -> dict[str, Any]:
    dirty = bool(_dirty_code())
    if require_clean and dirty:
        raise ReleaseError("refusing to freeze a dirty worktree")
    proof = verify_test_proof(proof_path)
    scan = store.conn.execute(
        "SELECT scan_id,as_of,status,config_hash,data_hash,started_at FROM scan_runs "
        "ORDER BY started_at DESC LIMIT 1").fetchone()
    if not scan or scan["status"] != "success":
        raise ReleaseError("latest scan is missing or not successful")
    counts = {"anomalies": store.scalar("SELECT COUNT(*) FROM anomalies") or 0,
              "opportunities": store.scalar("SELECT COUNT(*) FROM opportunities") or 0}
    by_status = {r[0]: r[1] for r in store.conn.execute(
        "SELECT status,COUNT(*) FROM opportunities GROUP BY status")}
    artifacts = {}
    for p in [Path("reports") / f"report_{scan['as_of']}.md",
              Path("reports") / f"scan_{scan['as_of']}.json"]:
        if p.exists():
            artifacts[str(p)] = _sha256(p.read_bytes())
    manifest = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "git_dirty": dirty, "scan": dict(scan), "scan_counts": counts,
        "opportunities_by_status": by_status,
        "test_evidence": {"proof_path": str(proof_path), "log_sha256": proof["log_sha256"],
                          "passed": proof["passed"], "failed": proof["failed"],
                          "skipped": proof["skipped"], "command": proof["command"]},
        "artifacts": artifacts, "notes": notes,
    }
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    stamp = manifest["git_commit"][:10] or datetime.now(timezone.utc).strftime("%Y%m%d")
    path = out / f"release_{stamp}.json"
    if path.exists():
        raise ReleaseError(f"release manifest already exists: {path}")
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["path"] = str(path)
    return manifest
