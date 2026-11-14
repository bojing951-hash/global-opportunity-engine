"""End-to-end proofs for the release gate (P1-01 / P1-02).

These tests build a throwaway git repository so the gate can be exercised for
real (collect -> run -> junit -> proof -> verify -> re-run) without touching the
real suite or the real release directory.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import goe.release as rel


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(root), capture_output=True, text=True, check=True
    ).stdout.strip()


def _make_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\naddopts = '-q'\n", encoding="utf-8"
    )
    (root / "tests" / "test_a.py").write_text(
        "def test_one():\n    assert True\n\ndef test_two():\n    assert True\n",
        encoding="utf-8",
    )
    (root / "tests" / "test_b.py").write_text("def test_three():\n    assert True\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "test")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "init")
    return root


@pytest.fixture()
def small_repo(tmp_path, monkeypatch):
    monkeypatch.setitem(rel.MIN_REQUIRED, "offline", 3)
    return _make_repo(tmp_path)


def test_proof_runs_full_collected_set_and_verifies(small_repo):
    proof = rel.run_test_proof(cwd=small_repo)
    assert proof["passed"] == 3
    assert proof["required"]["count"] == 3
    assert proof["executed"]["count"] == 3
    # portable by construction: no interpreter path, no absolute paths in evidence
    assert proof["command_template"][0] == rel.PYTHON_PLACEHOLDER
    assert proof["command_template"].count(rel.JUNIT_PLACEHOLDER) == 1
    raw = Path(proof["proof_path"]).read_text(encoding="utf-8")
    assert str(small_repo) not in raw, "proof file must not embed an absolute path"
    verified = rel.verify_test_proof(proof["proof_path"], cwd=small_repo, rerun=True)
    assert verified["rerun"]["passed"] == 3
    assert verified["rerun"]["executed"] == 3


def test_proof_survives_a_fresh_clone(small_repo, tmp_path):
    proof = rel.run_test_proof(cwd=small_repo)
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(small_repo), str(clone)], check=True)
    shutil.copytree(small_repo / "audit" / "test_evidence", clone / "audit" / "test_evidence")
    copied = clone / Path(proof["proof_path"]).relative_to(small_repo)
    verified = rel.verify_test_proof(copied, cwd=clone, rerun=True)
    assert verified["rerun"]["passed"] == 3


def test_env_var_override_cannot_shrink_the_suite(small_repo, monkeypatch):
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k test_one")
    proof = rel.run_test_proof(cwd=small_repo)
    assert proof["passed"] == 3, "PYTEST_ADDOPTS must not narrow the released suite"


def test_injected_selector_is_rejected(small_repo):
    proof = rel.run_test_proof(cwd=small_repo)
    data = json.loads(Path(proof["proof_path"]).read_text())
    for extra in (["--ignore=tests/test_b.py"], ["--deselect", "tests/test_b.py::test_three"]):
        poisoned = dict(data, command_template=list(data["command_template"]) + extra)
        path = Path(proof["proof_path"]).with_name("poisoned.json")
        path.write_text(json.dumps(poisoned), encoding="utf-8")
        with pytest.raises(rel.ReleaseError, match="forbidden selector|canonical"):
            rel.verify_test_proof(path, cwd=small_repo, rerun=False)


def test_tampered_counts_are_rejected(small_repo):
    proof = rel.run_test_proof(cwd=small_repo)
    data = json.loads(Path(proof["proof_path"]).read_text())
    path = Path(proof["proof_path"]).with_name("tampered.json")
    for field, value in (("passed", 99), ("executed", {"count": 2, "sha256": "0" * 64})):
        bad = dict(data, **{field: value})
        path.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(rel.ReleaseError):
            rel.verify_test_proof(path, cwd=small_repo, rerun=False)


def test_deleting_tests_after_proof_is_rejected(small_repo):
    proof = rel.run_test_proof(cwd=small_repo)
    (small_repo / "tests" / "test_b.py").unlink()  # a real shrink, not a no-op rewrite
    _git(small_repo, "add", "-A")
    _git(small_repo, "commit", "-qm", "shrink")
    with pytest.raises(rel.ReleaseError):
        rel.verify_test_proof(proof["proof_path"], cwd=small_repo, rerun=False)


def test_floor_blocks_a_shrunken_suite(small_repo, monkeypatch):
    monkeypatch.setitem(rel.MIN_REQUIRED, "offline", 4)
    (small_repo / "tests" / "test_b.py").write_text("\n")
    _git(small_repo, "add", "-A")
    _git(small_repo, "commit", "-qm", "shrink")
    with pytest.raises(rel.ReleaseError, match="below the required floor"):
        rel.run_test_proof(cwd=small_repo)


def test_release_manifest_rejects_network_category(monkeypatch, small_repo, tmp_path):
    """A 9-test network proof must never back a release."""
    proof = rel.run_test_proof(cwd=small_repo)
    forged = dict(proof, category="network", marker_expr=rel.CATEGORY_MARKERS["network"],
                  command_template=rel.command_template("network"))
    monkeypatch.setattr(rel, "verify_test_proof", lambda *a, **k: forged)
    monkeypatch.setattr(rel, "_dirty_code", lambda **k: False)
    monkeypatch.setattr(rel, "_git_root", lambda *a, **k: tmp_path.resolve())
    monkeypatch.setattr(rel, "_git", lambda *a, **k: "abc123")
    with pytest.raises(rel.ReleaseError, match="release requires"):
        rel.build_manifest(store=object(), proof_path=proof["proof_path"])


def test_verify_release_cli_rejects_bad_proof(tmp_path):
    """The portable verifier must fail closed on a missing/forged proof."""
    from goe import cli as goe_cli

    class Args:
        proof = str(tmp_path / "missing.proof.json")
        no_rerun = True

    assert goe_cli.cmd_verify_release(Args()) == 1


# ---------------------------------------------------------------- red-team round 1


def test_root_pytest_module_cannot_shadow_the_runner(small_repo):
    """P0: a repo-root pytest.py must not be able to fake the whole run."""
    (small_repo / "pytest.py").write_text(
        "import sys\nprint('188 passed in 0.01s')\nsys.exit(0)\n", encoding="utf-8"
    )
    _git(small_repo, "add", "-A")
    _git(small_repo, "commit", "-qm", "shadow")
    proof = rel.run_test_proof(cwd=small_repo)
    assert proof["passed"] == 3, "the real pytest suite must be the one that ran"


def test_skipped_tests_are_not_accepted(small_repo):
    """P0: 1 passed + N skipped must never look like a full pass."""
    (small_repo / "tests" / "conftest.py").write_text(
        "import pytest\n\n"
        "def pytest_collection_modifyitems(items):\n"
        "    for item in items:\n"
        "        item.add_marker(pytest.mark.skip(reason='x'))\n",
        encoding="utf-8",
    )
    _git(small_repo, "add", "-A")
    _git(small_repo, "commit", "-qm", "skip-all")
    with pytest.raises(rel.ReleaseError, match="not clean|junit|skipped"):
        rel.run_test_proof(cwd=small_repo)


def test_assume_unchanged_is_treated_as_dirty(small_repo):
    """P1: index flags must not hide a local edit from the clean-tree check."""
    _git(small_repo, "update-index", "--assume-unchanged", "tests/test_a.py")
    (small_repo / "tests" / "test_a.py").write_text("def test_one():\n    pass\n", encoding="utf-8")
    assert rel._dirty_code(cwd=small_repo) is True


def test_core_worktree_decoy_is_rejected(small_repo, tmp_path):
    """P1: git must not be able to point the gate at a different tree."""
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    _git(small_repo, "config", "core.worktree", str(decoy))
    with pytest.raises(rel.ReleaseError, match="does not contain|decoy"):
        rel._git_root(small_repo)
    _git(small_repo, "config", "--unset", "core.worktree")


def test_absolute_evidence_path_is_rejected(small_repo, tmp_path):
    """P2: evidence must stay inside the repository and stay portable."""
    proof = rel.run_test_proof(cwd=small_repo)
    data = json.loads(Path(proof["proof_path"]).read_text(encoding="utf-8"))
    data["junit_path"] = str(Path(proof["junit_path"]).resolve())
    bad = Path(proof["proof_path"]).with_name("absolute.json")
    bad.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(rel.ReleaseError, match="repo-relative|escapes"):
        rel.verify_test_proof(bad, cwd=small_repo, rerun=False)


# ---------------------------------------------------------------- red-team round 2


def test_untracked_root_conftest_cannot_change_the_run(small_repo):
    """P1: a conftest hidden from git must not exist in the executed tree."""
    (small_repo / "conftest.py").write_text(
        "import pytest\n\n"
        "def pytest_collection_modifyitems(items):\n"
        "    for item in items:\n"
        "        item.add_marker(pytest.mark.skip(reason='hidden'))\n",
        encoding="utf-8",
    )
    (small_repo / ".git" / "info" / "exclude").write_text("conftest.py\n", encoding="utf-8")
    assert rel._dirty_code(cwd=small_repo) is False, "git cannot see the excluded file"
    proof = rel.run_test_proof(cwd=small_repo)
    assert proof["passed"] == 3 and proof["skipped"] == 0


def test_verify_rejects_a_dirty_worktree(small_repo):
    """P1: replaying on a dirty tree could run a different test body."""
    proof = rel.run_test_proof(cwd=small_repo)
    (small_repo / "tests" / "test_a.py").write_text(
        "def test_one():\n    assert False\n\ndef test_two():\n    assert True\n", encoding="utf-8"
    )
    with pytest.raises(rel.ReleaseError, match="dirty worktree"):
        rel.verify_test_proof(proof["proof_path"], cwd=small_repo, rerun=False)


def test_git_failure_is_fail_closed(tmp_path):
    """P1: a failed git call must raise, not look clean."""
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(rel.ReleaseError, match="git "):
        rel._dirty_code(cwd=plain)


def test_ancestor_worktree_decoy_is_rejected(small_repo):
    """P2: root must be exactly the directory being released, not an ancestor."""
    inner = small_repo / "inner"
    inner.mkdir()
    decoy = small_repo.parent / "outer-decoy"
    decoy.mkdir(exist_ok=True)
    _git(small_repo, "config", "core.worktree", str(decoy))
    try:
        with pytest.raises(rel.ReleaseError, match="must run at the repository root|decoy"):
            rel._git_root(inner, exact=True)
    finally:
        _git(small_repo, "config", "--unset", "core.worktree")


def test_root_doc_change_after_proof_is_allowed(small_repo):
    """P1 regression: docs-only commits after the proof must remain replayable."""
    proof = rel.run_test_proof(cwd=small_repo)
    (small_repo / "PROJECT_STATE.md").write_text("# state\n", encoding="utf-8")
    _git(small_repo, "add", "-A")
    _git(small_repo, "commit", "-qm", "docs")
    rel.verify_test_proof(proof["proof_path"], cwd=small_repo, rerun=False)


def test_export_ignore_cannot_hide_a_failing_test(small_repo):
    """P1 round 3: git archive honours export-ignore; the gate must not."""
    (small_repo / "tests" / "test_zz_fail.py").write_text(
        "def test_must_fail():\n    assert False\n", encoding="utf-8"
    )
    (small_repo / ".gitattributes").write_text(
        "tests/test_zz_fail.py export-ignore\n", encoding="utf-8"
    )
    _git(small_repo, "add", "-A")
    _git(small_repo, "commit", "-qm", "hidden failure")
    with pytest.raises(rel.ReleaseError, match="not clean|did not pass"):
        rel.run_test_proof(cwd=small_repo)
