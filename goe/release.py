"""Release gate with machine-verifiable, portable test evidence.

Design contract (v2)
--------------------
A release manifest may only be built from a test proof that the gate can
*re-execute itself* on the current commit. Nothing in the proof file is trusted
as a claim about what ran; the proof is only a record that is cross-checked
against a fresh run.

Root causes addressed:

* P1-01 (partial suites accepted): the caller can no longer pass a command.
  The gate builds the pytest invocation itself, rejects any argv that is not
  byte-equal to the canonical template (so ``--ignore``, ``--ignore-glob``,
  ``--deselect``, ``-k``, a custom ``-m``, ``-c``, ``-p``, ``-o addopts=...``
  and positional node ids are all rejected), clears pytest env vars, and
  compares the *actual collected node ids* with the *executed* node ids parsed
  from JUnit XML. A proof whose executed set is not identical to the collected
  set is rejected. A minimum test floor per category blocks silent shrinkage.
* P1-02 (non-portable evidence): proofs store a command *template* with
  ``{python}`` / ``{junit}`` placeholders and repo-relative paths only. Any
  Python >= 3.10 interpreter in a fresh clone can re-run the proof.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .db import Store

PROOF_SCHEMA = "goe-test-proof/v2"
PYTHON_PLACEHOLDER = "{python}"
JUNIT_PLACEHOLDER = "{junit}"

#: suite categories with independent acceptance requirements
CATEGORY_MARKERS: dict[str, str] = {
    "offline": "not network and not realdata",
    "network": "network and not realdata",
    "realdata": "realdata",
}
DEFAULT_CATEGORY = "offline"

#: anti-shrink floors. Raise these when tests are legitimately added; never lower
#: them without a reviewed contract change.
MIN_REQUIRED: dict[str, int] = {"offline": 186, "network": 9, "realdata": 1}

#: pytest environment variables that can change collection/selection/plugins
_HARDENED_ENV = (
    "PYTEST_ADDOPTS",
    "PYTEST_PLUGINS",
    "PYTEST_CFG",
    "PYTEST_DEBUG",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
)

#: argv tokens that can never appear in a release proof command
FORBIDDEN_ARGS = (
    "--ignore",
    "--ignore-glob",
    "--deselect",
    "--lf",
    "--ff",
    "--sw",
    "--co",
    "--collect-only",
    "--pyargs",
    "-c",
    "-p",
    "-k",
    "-m",
    "-o",
    "::",
)


class ReleaseError(RuntimeError):
    pass


# --------------------------------------------------------------------------- io


def _git(*args: str, cwd: str | Path = ".") -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return ""


def _git_root(cwd: str | Path = ".") -> Path:
    root = _git("rev-parse", "--show-toplevel", cwd=cwd)
    if not root:
        raise ReleaseError("not inside a git repository")
    return Path(root).resolve()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_json(obj: Any) -> str:
    return _sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def _clean_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in _HARDENED_ENV}
    env.pop("PYTHONPATH", None)
    return env


def _dirty_code(*, cwd: str | Path = ".") -> bool:
    """Dirty means code/config/docs changed; generated proof/manifest files are exempt."""
    lines = _git("-C", str(cwd), "status", "--porcelain").splitlines()
    allowed = ("audit/test_evidence/", "audit/releases/")
    for line in lines:
        if not line.strip():
            continue
        path = line[3:].strip()
        paths = [p.strip() for p in path.split(" -> ")] if " -> " in path else [path]
        if any(not part.startswith(allowed) for part in paths):
            return True
    return False


def _parse_pytest(output: str) -> dict[str, int]:
    def one(pattern: str) -> int:
        m = re.search(pattern, output)
        return int(m.group(1)) if m else 0

    tail = "\n".join(
        [
            ln
            for ln in output.splitlines()
            if re.search(r"\d+ (passed|failed|skipped|deselected|error)", ln)
        ][-5:]
    )
    return {
        "passed": one(r"(\d+) passed"),
        "failed": one(r"(\d+) failed"),
        "skipped": one(r"(\d+) skipped"),
        "deselected": one(r"(\d+) deselected"),
        "errors": one(r"(\d+) errors?"),
    }


# --------------------------------------------------------------------- commands


def canonical_command(python: str, category: str, junit: str) -> list[str]:
    if category not in CATEGORY_MARKERS:
        raise ReleaseError(f"unknown test category: {category}")
    return [
        python,
        "-m",
        "pytest",
        "tests",
        "-o",
        "addopts=",
        "-q",
        "-m",
        CATEGORY_MARKERS[category],
        "--junitxml",
        junit,
    ]


def command_template(category: str) -> list[str]:
    return canonical_command(PYTHON_PLACEHOLDER, category, JUNIT_PLACEHOLDER)


def _assert_command_is_canonical(command: list[str], category: str) -> None:
    """Reject any argv that is not exactly the canonical template (defence in depth)."""
    text = " ".join(str(x) for x in command)
    for token in FORBIDDEN_ARGS:
        # "-m" / "-o" are legal only in their canonical positions, checked below.
        if token in ("-m", "-o"):
            continue
        if token in command or token in text:
            raise ReleaseError(f"proof command contains forbidden selector: {token}")
    if command != command_template(category):
        raise ReleaseError("proof command is not the canonical full-suite invocation")


# --------------------------------------------------------------- node id sets


def collect_node_ids(cwd: str | Path = ".", category: str = DEFAULT_CATEGORY) -> list[str]:
    """Collect every test node id that the canonical suite would run."""
    root = _git_root(cwd)
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "-o",
        "addopts=",
        "--collect-only",
        "-q",
        "-m",
        CATEGORY_MARKERS[category],
    ]
    proc = subprocess.run(
        cmd, cwd=str(root), capture_output=True, text=True, timeout=900, env=_clean_env()
    )
    ids = [
        ln.strip()
        for ln in proc.stdout.splitlines()
        if ln.strip().startswith("tests/") and "::" in ln
    ]
    if proc.returncode != 0:
        raise ReleaseError(f"test collection failed: rc={proc.returncode}")
    if not ids:
        raise ReleaseError("test collection produced no node ids")
    return sorted(set(ids))


def executed_node_ids(junit_path: str | Path, expected: list[str]) -> list[str]:
    """Map JUnit testcases back to node ids, resolving the file from collected ids."""
    files = {nid.split("::", 1)[0] for nid in expected}
    path = Path(junit_path)
    if not path.exists():
        raise ReleaseError(f"junit evidence missing: {path}")
    root = ET.parse(path).getroot()
    out: list[str] = []
    for case in root.iter("testcase"):
        classname = case.get("classname", "") or ""
        name = case.get("name", "") or ""
        parts = classname.split(".") if classname else []
        resolved = None
        for k in range(len(parts), 0, -1):
            candidate = "/".join(parts[:k]) + ".py"
            if candidate in files:
                resolved = (candidate, ".".join(parts[k:]))
                break
        if resolved is None:
            # fall back to the historical tests.<module> convention
            if len(parts) >= 2 and parts[0] == "tests":
                resolved = ("/".join(parts[:2]) + ".py", ".".join(parts[2:]))
            else:
                raise ReleaseError(f"cannot resolve junit testcase to a file: {classname}")
        file, cls = resolved
        node = file + "::" + (cls + "::" if cls else "") + name
        out.append(node)
    if not out:
        raise ReleaseError("junit evidence contains no testcases")
    return sorted(out)


def _required_set(expected: list[str]) -> dict[str, Any]:
    return {"count": len(expected), "sha256": _sha256_json(expected)}


# ------------------------------------------------------------------ proof flow


def run_test_proof(
    *,
    cwd: str | Path = ".",
    category: str = DEFAULT_CATEGORY,
    log_dir: str | Path = "audit/test_evidence",
    timeout: int = 3600,
) -> dict[str, Any]:
    """Run the canonical suite and write an immutable, portable proof file.

    The caller cannot influence the pytest invocation: there is no ``command``
    parameter by design (root cause of P1-01).
    """
    root = _git_root(cwd)
    if category not in CATEGORY_MARKERS:
        raise ReleaseError(f"unknown test category: {category}")
    commit = _git("rev-parse", "HEAD", cwd=root)
    if not commit:
        raise ReleaseError("cannot establish git commit for test proof")
    if _dirty_code(cwd=root):
        raise ReleaseError("test proof requires a clean worktree")

    expected = collect_node_ids(root, category)
    if len(expected) < MIN_REQUIRED[category]:
        raise ReleaseError(
            f"{category} suite collected {len(expected)} tests, "
            f"below the required floor of {MIN_REQUIRED[category]}"
        )

    tmpdir = Path(tempfile.mkdtemp(prefix="goe-junit-"))
    junit_tmp = tmpdir / "junit.xml"
    command = canonical_command(sys.executable, category, str(junit_tmp))
    started = datetime.now(timezone.utc)
    proc = subprocess.run(
        command,
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_clean_env(),
    )
    ended = datetime.now(timezone.utc)
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    counts = _parse_pytest(output)
    if proc.returncode != 0 or counts["failed"] or counts["errors"]:
        raise ReleaseError(f"test run failed: rc={proc.returncode} counts={counts}")
    if counts["passed"] <= 0:
        raise ReleaseError("test run reported no passed tests")

    executed = executed_node_ids(junit_tmp, expected)
    if set(executed) != set(expected):
        missing = sorted(set(expected) - set(executed))[:5]
        extra = sorted(set(executed) - set(expected))[:5]
        raise ReleaseError(
            f"executed test set differs from collected set "
            f"(missing={len(set(expected) - set(executed))} {missing}, "
            f"extra={len(set(executed) - set(expected))} {extra})"
        )

    evidence_dir = Path(root) / log_dir
    evidence_dir.mkdir(parents=True, exist_ok=True)
    stamp = ended.strftime("%Y%m%dT%H%M%SZ")
    base = f"{stamp}_{commit[:10]}"
    log_path = evidence_dir / f"{base}.log"
    junit_path = evidence_dir / f"{base}.junit.xml"
    log_path.write_text(output, encoding="utf-8")
    junit_path.write_bytes(junit_tmp.read_bytes())

    proof: dict[str, Any] = {
        "schema": PROOF_SCHEMA,
        "git_commit": commit,
        "git_dirty": False,
        "category": category,
        "marker_expr": CATEGORY_MARKERS[category],
        "command_template": command_template(category),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "python_requires": ">=3.10",
        "cwd_rel": ".",
        "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ended_at": ended.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "exit_code": proc.returncode,
        **counts,
        "required": _required_set(expected),
        "executed": {
            "count": len(executed),
            "sha256": _sha256_json(executed),
        },
        "log_path": str(log_path.relative_to(root)),
        "log_sha256": _sha256(log_path.read_bytes()),
        "junit_path": str(junit_path.relative_to(root)),
        "junit_sha256": _sha256(junit_path.read_bytes()),
    }
    proof_path = evidence_dir / f"{base}.proof.json"
    proof_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    proof["proof_path"] = str(proof_path)
    return proof


def _load_proof(proof_path: str | Path) -> dict[str, Any]:
    path = Path(proof_path)
    if not path.exists():
        raise ReleaseError(f"test proof missing: {path}")
    try:
        proof = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReleaseError(f"test proof is not valid JSON: {exc}") from exc
    if proof.get("schema") != PROOF_SCHEMA:
        raise ReleaseError(f"unknown test proof schema: {proof.get('schema')!r}")
    return proof


def _check_commit(proof: dict[str, Any], root: Path) -> None:
    commit = _git("rev-parse", "HEAD", cwd=root)
    proof_commit = proof.get("git_commit")
    if not proof_commit:
        raise ReleaseError("test proof has no git commit")
    if proof_commit == commit:
        return
    ancestor = (
        subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", proof_commit, commit],
            capture_output=True,
        ).returncode
        == 0
    )
    changed = _git("-C", str(root), "diff", "--name-only", proof_commit, commit).splitlines()
    allowed = ("audit/", "evaluation/", "docs/", "README.md", "TEST_RESULTS.md")
    if not ancestor or any(not p.startswith(allowed) for p in changed if p.strip()):
        raise ReleaseError("test proof commit is not an ancestor with only evidence/docs changes")
    code_changed = _git(
        "-C", str(root), "diff", "--name-only", proof_commit, commit,
        "--", "goe", "tests", "config", "contracts", "pyproject.toml",
    )
    if code_changed:
        raise ReleaseError("code/config/tests changed after test proof")


def verify_test_proof(
    proof_path: str | Path,
    *,
    cwd: str | Path = ".",
    rerun: bool = True,
) -> dict[str, Any]:
    """Verify a proof. With ``rerun=True`` (default) the gate re-executes the suite."""
    proof = _load_proof(proof_path)
    root = _git_root(cwd)
    _check_commit(proof, root)

    category = proof.get("category")
    if category not in CATEGORY_MARKERS:
        raise ReleaseError(f"unknown test category in proof: {category!r}")
    if proof.get("marker_expr") != CATEGORY_MARKERS[category]:
        raise ReleaseError("proof marker expression does not match its category")
    _assert_command_is_canonical([str(x) for x in proof.get("command_template", [])], category)

    if proof.get("git_dirty"):
        raise ReleaseError("test proof was created on a dirty worktree")
    if proof.get("exit_code") != 0 or int(proof.get("failed", 0)) or int(proof.get("errors", 0)):
        raise ReleaseError("test proof records failed tests")
    if int(proof.get("passed", 0)) <= 0:
        raise ReleaseError("test proof records no passed tests")

    recorded_py = str(proof.get("python_version", ""))
    current_py = f"{sys.version_info.major}.{sys.version_info.minor}"
    if recorded_py != current_py:
        raise ReleaseError(
            f"proof python {recorded_py} does not match current interpreter {current_py}"
        )

    expected = collect_node_ids(root, category)
    if len(expected) < MIN_REQUIRED[category]:
        raise ReleaseError(
            f"{category} suite collected {len(expected)} tests, "
            f"below the required floor of {MIN_REQUIRED[category]}"
        )
    replay_required = _required_set(expected)
    if recorded := proof.get("required"):
        if int(recorded.get("count", -1)) != replay_required["count"]:
            raise ReleaseError("required test count disagrees with current collection")
        if recorded.get("sha256") != replay_required["sha256"]:
            raise ReleaseError("required test set hash disagrees with current collection")
    else:
        raise ReleaseError("proof has no required test set")

    junit_rel = proof.get("junit_path")
    if not junit_rel:
        raise ReleaseError("proof has no junit evidence")
    junit_path = root / junit_rel
    if not junit_path.exists():
        raise ReleaseError("junit evidence is missing")
    if _sha256(junit_path.read_bytes()) != proof.get("junit_sha256"):
        raise ReleaseError("junit evidence hash mismatch")
    executed = executed_node_ids(junit_path, expected)
    if set(executed) != set(expected):
        raise ReleaseError("recorded executed set is not identical to the collected set")
    if int(proof.get("executed", {}).get("count", -1)) != len(executed):
        raise ReleaseError("executed count disagrees with junit evidence")
    if proof.get("executed", {}).get("sha256") != _sha256_json(executed):
        raise ReleaseError("executed set hash disagrees with junit evidence")

    log_rel = proof.get("log_path")
    log_path = root / str(log_rel)
    if not log_path.exists():
        raise ReleaseError("test proof log is missing")
    if _sha256(log_path.read_bytes()) != proof.get("log_sha256"):
        raise ReleaseError("test proof log hash mismatch")
    log_counts = _parse_pytest(log_path.read_text(encoding="utf-8", errors="replace"))
    for key in ("passed", "failed", "skipped", "errors"):
        if int(proof.get(key, -1)) != int(log_counts.get(key, -2)):
            raise ReleaseError(f"test proof {key} count disagrees with log")

    if rerun:
        tmpdir = Path(tempfile.mkdtemp(prefix="goe-rerun-"))
        junit_tmp = tmpdir / "junit.xml"
        cmd = canonical_command(sys.executable, category, str(junit_tmp))
        proc = subprocess.run(
            cmd, cwd=str(root), capture_output=True, text=True, timeout=3600, env=_clean_env()
        )
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
        rerun_counts = _parse_pytest(output)
        if proc.returncode != 0 or rerun_counts["failed"] or rerun_counts["errors"]:
            raise ReleaseError(f"independent re-execution failed: rc={proc.returncode}")
        rerun_executed = executed_node_ids(junit_tmp, expected)
        if set(rerun_executed) != set(expected):
            raise ReleaseError("re-execution did not run the full collected test set")
        if rerun_counts["passed"] != int(proof.get("passed", -1)):
            raise ReleaseError("re-execution passed count differs from the recorded proof")
        proof = dict(proof)
        proof["rerun"] = {
            "passed": rerun_counts["passed"],
            "executed": len(rerun_executed),
            "log_sha256": _sha256(output.encode("utf-8")),
        }
    return proof


def build_manifest(
    store: Store,
    *,
    proof_path: str | Path,
    out_dir: str | Path = "audit/releases",
    notes: str = "",
    require_clean: bool = True,
) -> dict[str, Any]:
    """Freeze a release manifest. The proof is re-executed, never trusted."""
    root = _git_root(".")
    dirty = bool(_dirty_code(cwd=root))
    if require_clean and dirty:
        raise ReleaseError("refusing to freeze a dirty worktree")
    proof = verify_test_proof(proof_path, cwd=root, rerun=True)

    scan = store.conn.execute(
        "SELECT scan_id,as_of,status,config_hash,data_hash,started_at FROM scan_runs "
        "ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    if not scan or scan["status"] != "success":
        raise ReleaseError("latest scan is missing or not successful")
    counts = {
        "anomalies": store.scalar("SELECT COUNT(*) FROM anomalies") or 0,
        "opportunities": store.scalar("SELECT COUNT(*) FROM opportunities") or 0,
    }
    by_status = {
        r[0]: r[1]
        for r in store.conn.execute("SELECT status,COUNT(*) FROM opportunities GROUP BY status")
    }
    artifacts = {}
    for p in [
        Path("reports") / f"report_{scan['as_of']}.md",
        Path("reports") / f"scan_{scan['as_of']}.json",
    ]:
        if p.exists():
            artifacts[str(p)] = _sha256(p.read_bytes())
    manifest = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _git("rev-parse", "HEAD", cwd=root),
        "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD", cwd=root),
        "git_dirty": dirty,
        "scan": dict(scan),
        "scan_counts": counts,
        "opportunities_by_status": by_status,
        "test_evidence": {
            "proof_path": str(proof_path),
            "category": proof["category"],
            "passed": proof["passed"],
            "skipped": proof["skipped"],
            "commands": proof["command_template"],
            "required_sha256": proof["required"]["sha256"],
            "executed_sha256": proof["executed"]["sha256"],
            "rerun": proof.get("rerun"),
        },
        "artifacts": artifacts,
        "notes": notes,
    }
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = manifest["git_commit"][:10] or datetime.now(timezone.utc).strftime("%Y%m%d")
    path = out / f"release_{stamp}.json"
    if path.exists():
        raise ReleaseError(f"release manifest already exists: {path}")
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["path"] = str(path)
    return manifest
