"""Release gate with machine-verifiable, portable test evidence (v3).

Threat model
------------
The proof file itself is attacker-writable, so nothing in it is trusted as a
claim about what ran. The gate *re-executes* the suite and compares the executed
set to the collected set.

Hardening added after red-team round 1 (see ``audit/QA_REDTEAM_RELEASE.md``):

* trusted pytest launcher — ``python -c`` with cwd removed from ``sys.path`` so a
  repository-root ``pytest.py``/``pytest/`` cannot shadow the real pytest;
* skipped/failed/errored testcases do not count as executed — a run must have
  ``passed == required == executed`` and ``skipped == 0``;
* counts come from the JUnit ``<testsuite>`` attributes, not from console text;
* git calls run with ``GIT_*`` stripped and the reported root must contain the
  working directory (blocks ``core.worktree`` / ``GIT_DIR`` decoys);
* ``assume-unchanged`` / ``skip-worktree`` index flags are rejected as dirty;
* evidence paths must stay inside the repository (no absolute paths);
* JUnit classname resolution must map to exactly one collected node id;
* only ``offline`` proofs may back a release; only evidence/docs may change
  between proof commit and release commit.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .db import Store

PROOF_SCHEMA = "goe-test-proof/v4"
PYTHON_PLACEHOLDER = "{python}"
JUNIT_PLACEHOLDER = "{junit}"

#: trusted launcher: drop cwd from sys.path before importing pytest, then run it
PYTEST_LAUNCHER = (
    "import os,sys;"
    "sys.path=[p for p in sys.path if p not in ('', '.')];"
    "import pytest;"            # resolve the real pytest before the tree is on sys.path
    "sys.path.insert(0, os.getcwd());"  # then prefer the tree's own package over installed copies
    "raise SystemExit(pytest.main(sys.argv[1:]))"
)

CATEGORY_MARKERS: dict[str, str] = {
    "offline": "not network and not realdata",
    "network": "network and not realdata",
    "realdata": "realdata",
}
DEFAULT_CATEGORY = "offline"
RELEASE_CATEGORY = "offline"
MIN_REQUIRED: dict[str, int] = {"offline": 200, "network": 9, "realdata": 1}

_HARDENED_ENV = (
    "PYTHONOPTIMIZE",
    "PYTHONINSPECT",
    "PYTEST_ADDOPTS",
    "PYTEST_PLUGINS",
    "PYTEST_CFG",
    "PYTEST_DEBUG",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
)
_GIT_ENV_PREFIXES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CONFIG", "GIT_OBJECT_DIRECTORY")

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
    "-p",
    "-k",
    "::",
)
_EVIDENCE_ALLOWED = ("audit/test_evidence/", "audit/releases/")


class ReleaseError(RuntimeError):
    pass


# --------------------------------------------------------------------------- io


def _clean_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in _HARDENED_ENV}
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    # keep the launch directory off sys.path at interpreter startup, so a repo-root
    # sitecustomize.py / pytest.py cannot execute before the trusted launcher
    env["PYTHONSAFEPATH"] = "1"
    return env


def _git_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith(_GIT_ENV_PREFIXES)}


def _git(*args: str, cwd: str | Path = ".") -> str:
    """Strict git: a failing command is an error, never a silent empty string."""
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, env=_git_env()
    )
    if proc.returncode != 0:
        raise ReleaseError(f"git {' '.join(args)} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout.strip()


def _git_root(cwd: str | Path = ".", *, exact: bool = False) -> Path:
    cwd_abs = Path(cwd).resolve()
    root = _git("rev-parse", "--show-toplevel", cwd=cwd_abs)
    if not root:
        raise ReleaseError("not inside a git repository")
    root_path = Path(root).resolve()
    if exact and root_path != cwd_abs:
        raise ReleaseError(f"release operations must run at the repository root ({root_path})")
    if root_path != cwd_abs and root_path not in cwd_abs.parents:
        raise ReleaseError(
            f"git reported root {root_path} which does not contain {cwd_abs} "
            "(possible core.worktree / GIT_DIR decoy)"
        )
    return root_path


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_json(obj: Any) -> str:
    return _sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def _dirty_code(*, cwd: str | Path = ".") -> bool:
    """Dirty means code/config/docs changed; generated proof/manifest files are exempt."""
    for line in _git("-C", str(cwd), "ls-files", "-v").splitlines():
        if line[:1] in ("h", "S", "s"):
            return True  # assume-unchanged / skip-worktree can hide local edits
    lines = _git("-C", str(cwd), "status", "--porcelain", "--untracked-files=all").splitlines()
    for line in lines:
        if not line.strip():
            continue
        path = line[3:].strip()
        paths = [p.strip() for p in path.split(" -> ")] if " -> " in path else [path]
        if any(not part.startswith(_EVIDENCE_ALLOWED) for part in paths):
            return True
    return False


# --------------------------------------------------------------------- commands


def canonical_command(python: str, category: str, junit: str) -> list[str]:
    if category not in CATEGORY_MARKERS:
        raise ReleaseError(f"unknown test category: {category}")
    return [
        python,
        "-c",
        PYTEST_LAUNCHER,
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
    text = " ".join(str(x) for x in command)
    for token in FORBIDDEN_ARGS:
        if token in command or token in text:
            raise ReleaseError(f"proof command contains forbidden selector: {token}")
    if command != command_template(category):
        raise ReleaseError("proof command is not the canonical full-suite invocation")


# --------------------------------------------------------------- node id sets


def _blob_hash(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()


def _export_tree(root: Path, commit: str) -> Path:
    """Materialise exactly the committed tree, then prove it matches the commit.

    ``git archive`` is deliberately NOT used: it honours ``export-ignore`` /
    ``export-subst`` attributes, so a committed failing test could be filtered
    out of the "clean" tree (red-team round 3, P1). A detached worktree is a real
    checkout; every file is then compared with its ``ls-tree`` blob hash so a
    smudge filter or attribute trick cannot change the content either.
    """
    dest = Path(tempfile.mkdtemp(prefix="goe-tree-"))
    proc = subprocess.run(
        ["git", "-C", str(root), "worktree", "add", "--detach", "--quiet", str(dest), commit],
        capture_output=True,
        text=True,
        env=_git_env(),
    )
    if proc.returncode != 0:
        raise ReleaseError(
            f"cannot materialise tree for {commit[:10]}: {proc.stderr.strip()[:200]}"
        )
    try:
        entries = _git(
            "-c", "core.quotePath=false", "-C", str(root), "ls-tree", "-r", commit
        ).splitlines()
        expected: dict[str, str] = {}
        for line in entries:
            meta, path = line.split("\t", 1)
            mode, kind, sha = meta.split()[:3]
            if kind != "blob":
                raise ReleaseError(f"unsupported tree entry {kind}: {path}")
            expected[path] = sha
        present = sorted(
            p.relative_to(dest).as_posix()
            for p in dest.rglob("*")
            if p.is_file() and not p.is_symlink() and ".git" not in p.parts
        )
        missing = sorted(set(expected) - set(present))
        extra = sorted(set(present) - set(expected))
        if missing or extra:
            raise ReleaseError(
                f"materialised tree differs from commit {commit[:10]}: "
                f"missing={missing[:3]} extra={extra[:3]}"
            )
        for path, sha in expected.items():
            data = (dest / path).read_bytes()
            if _blob_hash(data) != sha:
                raise ReleaseError(f"tree content differs from commit blob: {path}")
    except Exception:
        subprocess.run(
            ["git", "-C", str(root), "worktree", "remove", "--force", str(dest)],
            capture_output=True,
            env=_git_env(),
        )
        raise
    return dest


def _dispose_tree(root: Path, tree: Path) -> None:
    subprocess.run(
        ["git", "-C", str(root), "worktree", "remove", "--force", str(tree)],
        capture_output=True,
        env=_git_env(),
    )


def _collect_in(tree: Path, category: str = DEFAULT_CATEGORY) -> list[str]:
    cmd = [
        sys.executable,
        "-c",
        PYTEST_LAUNCHER,
        "tests",
        "-o",
        "addopts=",
        "--collect-only",
        "-q",
        "-m",
        CATEGORY_MARKERS[category],
    ]
    proc = subprocess.run(
        cmd, cwd=str(tree), capture_output=True, text=True, timeout=900, env=_clean_env()
    )
    ids = [
        ln.strip()
        for ln in proc.stdout.splitlines()
        if ln.strip().startswith("tests/") and "::" in ln
    ]
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        raise ReleaseError(f"test collection failed: rc={proc.returncode} :: {' | '.join(tail)}")
    if not ids:
        raise ReleaseError("test collection produced no node ids")
    return sorted(set(ids))


def _assert_no_test_file_is_hidden(tree: Path, expected: list[str]) -> None:
    """A committed tests/test_*.py may not vanish through collect_ignore / conftest tricks."""
    represented = {nid.split("::", 1)[0] for nid in expected}
    files = {
        p.relative_to(tree).as_posix()
        for p in (tree / "tests").rglob("test_*.py")
        if ".git" not in p.parts
    }
    hidden = sorted(files - represented)
    if hidden:
        raise ReleaseError(
            f"committed test files produced no collected tests: {hidden[:5]} "
            "(collect_ignore or conftest filtering is not allowed in a release)"
        )


def collect_node_ids(cwd: str | Path = ".", category: str = DEFAULT_CATEGORY) -> list[str]:
    return _collect_in(_git_root(cwd, exact=True), category)


def _junit_summary(junit_path: str | Path) -> dict[str, int]:
    path = Path(junit_path)
    if not path.exists():
        raise ReleaseError(f"junit evidence missing: {path}")
    root_el = ET.parse(path).getroot()
    suites = [e for e in list(root_el) if e.tag == "testsuite"] or (
        [root_el] if root_el.tag == "testsuite" else []
    )
    if not suites:
        raise ReleaseError("junit evidence has no testsuite element")

    def total(attr: str) -> int:
        out = 0
        for suite in suites:
            raw = suite.get(attr, "0") or "0"
            try:
                out += int(raw)
            except ValueError as exc:
                raise ReleaseError(f"junit attribute {attr}={raw!r} is not an integer") from exc
        return out

    return {
        "tests": total("tests"),
        "failures": total("failures"),
        "errors": total("errors"),
        "skipped": total("skipped"),
    }


def executed_node_ids(junit_path: str | Path, expected: list[str]) -> list[str]:
    """Map JUnit testcases to collected node ids; fail closed on ambiguity."""
    expected_set = set(expected)
    path = Path(junit_path)
    if not path.exists():
        raise ReleaseError(f"junit evidence missing: {path}")
    root = ET.parse(path).getroot()
    out: list[str] = []
    for case in root.iter("testcase"):
        outcome = {child.tag for child in case}
        if outcome & {"skipped", "failure", "error"}:
            raise ReleaseError(
                f"test did not pass: {case.get('classname')}::{case.get('name')} "
                f"({','.join(sorted(outcome & {'skipped', 'failure', 'error'}))})"
            )
        classname = case.get("classname", "") or ""
        name = case.get("name", "") or ""
        parts = classname.split(".") if classname else []
        candidates: set[str] = set()
        for k in range(1, len(parts) + 1):
            file = "/".join(parts[:k]) + ".py"
            cls = ".".join(parts[k:])
            node = file + "::" + (cls + "::" if cls else "") + name
            if node in expected_set:
                candidates.add(node)
        if len(candidates) != 1:
            raise ReleaseError(
                f"cannot resolve junit testcase {classname}::{name} to exactly one "
                f"collected node id (candidates={len(candidates)})"
            )
        out.append(candidates.pop())
    if not out:
        raise ReleaseError("junit evidence contains no testcases")
    return sorted(out)


def _required_set(expected: list[str]) -> dict[str, Any]:
    return {"count": len(expected), "sha256": _sha256_json(expected)}


def _run_suite(root: Path, category: str, junit_path: Path, timeout: int) -> tuple[subprocess.CompletedProcess, str]:
    command = canonical_command(sys.executable, category, str(junit_path))
    proc = subprocess.run(
        command, cwd=str(root), capture_output=True, text=True, timeout=timeout, env=_clean_env()
    )
    return proc, (proc.stdout or "") + "\n" + (proc.stderr or "")


# ------------------------------------------------------------------ proof flow


def run_test_proof(
    *,
    cwd: str | Path = ".",
    category: str = DEFAULT_CATEGORY,
    log_dir: str | Path = "audit/test_evidence",
    timeout: int = 3600,
) -> dict[str, Any]:
    """Run the canonical suite and write an immutable, portable proof file."""
    root = _git_root(cwd, exact=True)
    if category not in CATEGORY_MARKERS:
        raise ReleaseError(f"unknown test category: {category}")
    commit = _git("rev-parse", "HEAD", cwd=root)
    if not commit:
        raise ReleaseError("cannot establish git commit for test proof")
    if _dirty_code(cwd=root):
        raise ReleaseError("test proof requires a clean worktree")
    tree = _export_tree(root, commit)
    try:
        expected = _collect_in(tree, category)
        if len(expected) < MIN_REQUIRED[category]:
            raise ReleaseError(
                f"{category} suite collected {len(expected)} tests, "
                f"below the required floor of {MIN_REQUIRED[category]}"
            )
        _assert_no_test_file_is_hidden(tree, expected)

        tmpdir = Path(tempfile.mkdtemp(prefix="goe-junit-"))
        junit_tmp = tmpdir / "junit.xml"
        started = datetime.now(timezone.utc)
        proc, output = _run_suite(tree, category, junit_tmp, timeout)
        ended = datetime.now(timezone.utc)

        summary = _junit_summary(junit_tmp)
        if proc.returncode != 0 or summary["failures"] or summary["errors"] or summary["skipped"]:
            raise ReleaseError(f"test run not clean: rc={proc.returncode} junit={summary}")
        if summary["tests"] != len(expected):
            raise ReleaseError(
                f"junit recorded {summary['tests']} tests but {len(expected)} were collected"
            )

        executed = executed_node_ids(junit_tmp, expected)
        if set(executed) != set(expected) or len(executed) != len(expected):
            missing = sorted(set(expected) - set(executed))[:5]
            raise ReleaseError(f"executed set differs from collected set (missing={missing})")
        junit_bytes = junit_tmp.read_bytes()
    finally:
        _dispose_tree(root, tree)

    evidence_dir = Path(root) / log_dir
    evidence_dir.mkdir(parents=True, exist_ok=True)
    stamp = ended.strftime("%Y%m%dT%H%M%SZ")
    base = f"{stamp}_{commit[:10]}"
    log_path = evidence_dir / f"{base}.log"
    junit_path = evidence_dir / f"{base}.junit.xml"
    log_path.write_text(output, encoding="utf-8")
    junit_path.write_bytes(junit_bytes)

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
        "passed": summary["tests"],
        "failed": summary["failures"],
        "errors": summary["errors"],
        "skipped": summary["skipped"],
        "required": _required_set(expected),
        "executed": {"count": len(executed), "sha256": _sha256_json(executed)},
        "log_path": log_path.relative_to(root).as_posix(),
        "log_sha256": _sha256(log_path.read_bytes()),
        "junit_path": junit_path.relative_to(root).as_posix(),
        "junit_sha256": _sha256(junit_path.read_bytes()),
    }
    proof_path = evidence_dir / f"{base}.proof.json"
    proof_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
    proof["proof_path"] = str(proof_path)
    return proof


def _as_int(proof: dict[str, Any], key: str) -> int:
    value = proof.get(key)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ReleaseError(f"proof field {key!r} is not an integer: {value!r}") from exc


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
            env=_git_env(),
        ).returncode
        == 0
    )
    changed = _git("-C", str(root), "diff", "--name-only", proof_commit, commit).splitlines()
    allowed = ("audit/", "docs/")
    root_docs = {"README.md", "TEST_RESULTS.md", "PROJECT_STATE.md", "AGENTS.md", "AGENT_TASKS.md",
                 "ARCHITECTURE.md", "DECISIONS.md", "PROJECT_SPEC.md"}
    if not ancestor or any(
        not p.startswith(allowed) and p not in root_docs for p in changed if p.strip()
    ):
        raise ReleaseError("test proof commit is not an ancestor with only evidence/docs changes")
    code_changed = _git(
        "-C", str(root), "diff", "--name-only", proof_commit, commit,
        "--", "goe", "tests", "config", "contracts", "scripts", "pyproject.toml", "evaluation",
    )
    if code_changed:
        raise ReleaseError("code/config/tests changed after test proof")


def _relative_evidence(proof: dict[str, Any], root: Path, key: str) -> Path:
    raw = proof.get(key)
    if not raw:
        raise ReleaseError(f"proof has no {key}")
    candidate = Path(str(raw))
    if candidate.is_absolute():
        raise ReleaseError(f"{key} must be repo-relative, got an absolute path")
    resolved = (root / candidate).resolve()
    if root not in resolved.parents:
        raise ReleaseError(f"{key} escapes the repository root")
    return resolved


def verify_test_proof(
    proof_path: str | Path,
    *,
    cwd: str | Path = ".",
    rerun: bool = True,
) -> dict[str, Any]:
    proof = _load_proof(proof_path)
    root = _git_root(cwd, exact=True)
    if _dirty_code(cwd=root):
        raise ReleaseError("cannot verify a proof on a dirty worktree")
    _check_commit(proof, root)

    category = proof.get("category")
    if category not in CATEGORY_MARKERS:
        raise ReleaseError(f"unknown test category in proof: {category!r}")
    if proof.get("marker_expr") != CATEGORY_MARKERS[category]:
        raise ReleaseError("proof marker expression does not match its category")
    _assert_command_is_canonical([str(x) for x in proof.get("command_template", [])], category)

    if proof.get("git_dirty"):
        raise ReleaseError("test proof was created on a dirty worktree")
    if proof.get("exit_code") != 0 or _as_int(proof, "failed") or _as_int(proof, "errors"):
        raise ReleaseError("test proof records failed tests")
    if _as_int(proof, "skipped"):
        raise ReleaseError("test proof records skipped tests; a release requires a clean run")

    recorded_py = str(proof.get("python_version", ""))
    current_py = f"{sys.version_info.major}.{sys.version_info.minor}"
    if recorded_py != current_py:
        raise ReleaseError(f"proof python {recorded_py} does not match current interpreter {current_py}")

    tree = _export_tree(root, _git("rev-parse", "HEAD", cwd=root))
    try:
        return _verify_in_tree(proof, root, tree, category, rerun)
    finally:
        _dispose_tree(root, tree)


def _verify_in_tree(
    proof: dict[str, Any], root: Path, tree: Path, category: str, rerun: bool
) -> dict[str, Any]:
    expected = _collect_in(tree, category)
    if len(expected) < MIN_REQUIRED[category]:
        raise ReleaseError(
            f"{category} suite collected {len(expected)} tests, "
            f"below the required floor of {MIN_REQUIRED[category]}"
        )
    _assert_no_test_file_is_hidden(tree, expected)
    replay_required = _required_set(expected)
    recorded = proof.get("required")
    if not isinstance(recorded, dict):
        raise ReleaseError("proof has no required test set")
    try:
        recorded_count = int(recorded.get("count", -1))
    except (TypeError, ValueError) as exc:
        raise ReleaseError("required test count is not an integer") from exc
    if recorded_count != replay_required["count"]:
        raise ReleaseError("required test count disagrees with current collection")
    if recorded.get("sha256") != replay_required["sha256"]:
        raise ReleaseError("required test set hash disagrees with current collection")
    if _as_int(proof, "passed") != replay_required["count"]:
        raise ReleaseError("passed count does not equal the required test count")

    junit_path = _relative_evidence(proof, root, "junit_path")
    if not junit_path.exists():
        raise ReleaseError("junit evidence is missing")
    if _sha256(junit_path.read_bytes()) != proof.get("junit_sha256"):
        raise ReleaseError("junit evidence hash mismatch")
    summary = _junit_summary(junit_path)
    if summary["tests"] != replay_required["count"] or summary["skipped"]:
        raise ReleaseError(f"junit evidence is not a clean full run: {summary}")
    executed = executed_node_ids(junit_path, expected)
    if len(executed) != len(expected) or set(executed) != set(expected):
        raise ReleaseError("recorded executed set is not identical to the collected set")
    if _as_int(proof.get("executed") or {}, "count") != len(executed):
        raise ReleaseError("executed count disagrees with junit evidence")
    if proof.get("executed", {}).get("sha256") != _sha256_json(executed):
        raise ReleaseError("executed set hash disagrees with junit evidence")

    log_path = _relative_evidence(proof, root, "log_path")
    if not log_path.exists():
        raise ReleaseError("test proof log is missing")
    if _sha256(log_path.read_bytes()) != proof.get("log_sha256"):
        raise ReleaseError("test proof log hash mismatch")

    if rerun:
        tmpdir = Path(tempfile.mkdtemp(prefix="goe-rerun-"))
        junit_tmp = tmpdir / "junit.xml"
        proc, output = _run_suite(tree, category, junit_tmp, 3600)
        rerun_summary = _junit_summary(junit_tmp)
        if (
            proc.returncode != 0
            or rerun_summary["failures"]
            or rerun_summary["errors"]
            or rerun_summary["skipped"]
        ):
            raise ReleaseError(f"independent re-execution not clean: {rerun_summary}")
        rerun_executed = executed_node_ids(junit_tmp, expected)
        if len(rerun_executed) != len(expected) or set(rerun_executed) != set(expected):
            raise ReleaseError("re-execution did not run the full collected test set")
        if rerun_summary["tests"] != int(proof.get("passed", -1)):
            raise ReleaseError("re-execution test count differs from the recorded proof")
        proof = dict(proof)
        proof["rerun"] = {
            "passed": rerun_summary["tests"],
            "executed": len(rerun_executed),
            "skipped": rerun_summary["skipped"],
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
    if proof.get("category") != RELEASE_CATEGORY:
        raise ReleaseError(
            f"release requires the {RELEASE_CATEGORY!r} suite, got {proof.get('category')!r}"
        )

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
