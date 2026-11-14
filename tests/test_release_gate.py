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
    (small_repo / "tests" / "test_b.py").write_text("def test_three():\n    assert True\n")
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
    with pytest.raises(rel.ReleaseError, match="release requires"):
        rel.build_manifest(store=object(), proof_path=proof["proof_path"])


def test_verify_release_cli_rejects_bad_proof(tmp_path):
    """The portable verifier must fail closed on a missing/forged proof."""
    from goe import cli as goe_cli

    class Args:
        proof = str(tmp_path / "missing.proof.json")
        no_rerun = True

    assert goe_cli.cmd_verify_release(Args()) == 1
