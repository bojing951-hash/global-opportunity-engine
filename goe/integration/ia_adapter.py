"""Adapter to the existing ``investment-agent`` deep-research system.

Design constraints (from the project spec):
* the existing system must not be rewritten, replaced or broken;
* integration happens through a documented, versioned JSON handoff plus the
  investment-agent's own public CLI (``ia_cli.py research-run``);
* the adapter never writes into the investment-agent repository. Research
  output directories are passed explicitly with ``--out-dir``, defaulting to
  this engine's ``exports/ia_runs/``.

The investment-agent CLI surface used here (verified against the local checkout):
    python3 ia_cli.py research-run --question "<question>" [--out-dir DIR] [--fanout]
It performs an 11-step deterministic research pipeline and writes a report.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from ..db import Store


def parse_research_artifact(out_dir: str | Path, stdout: str = "",
                            min_mtime: datetime | None = None) -> dict[str, Any]:
    """Read the downstream RESEARCH semantics, not just the process exit code.

    The investment-agent completes with rc=0 even when the research result is
    rejected or has no evidence rows. Success therefore requires a structured
    artifact: ``run_ok`` true, at least one evidence row, and no failed pipeline
    step. Returns a dict with semantic_status / run_ok / n_evidence_rows /
    n_steps_failed / report_path / reason.
    """
    out = Path(out_dir)
    reports = sorted(out.rglob("report.json"), key=lambda p: p.stat().st_mtime, reverse=True) if out.exists() else []
    payload = None
    report_path = None
    if reports:
        report_path = reports[0]
        if min_mtime is not None:
            try:
                mt = datetime.fromtimestamp(report_path.stat().st_mtime, tz=timezone.utc)
                if mt < min_mtime - pd.Timedelta(seconds=2):
                    return {"semantic_status": "partial", "run_ok": None, "n_evidence_rows": None,
                            "n_steps_failed": None, "report_path": str(report_path),
                            "reason": "报告早于本次运行，拒绝复用陈旧 artifact"}
            except Exception:
                pass
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            payload = None
    if payload is None:
        # fall back to a JSON envelope on stdout (ia_cli prints one in some modes)
        for line in reversed((stdout or "").splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    cand = json.loads(line)
                except Exception:
                    continue
                if isinstance(cand, dict) and ("ok" in cand or "run_ok" in cand):
                    payload = cand
                    break
    if payload is None:
        return {"semantic_status": "partial", "run_ok": None, "n_evidence_rows": None,
                "n_steps_failed": None, "report_path": str(report_path) if report_path else None,
                "reason": "研究进程结束但未找到可解析的结构化报告"}

    run_ok = payload.get("run_ok")
    if run_ok is None:
        run_ok = payload.get("ok")
    evidence = payload.get("evidence_index")
    n_evidence = len(evidence) if isinstance(evidence, (list, dict)) else payload.get("n_evidence_rows")
    steps = payload.get("steps") or []
    n_steps_failed = sum(1 for st in steps if isinstance(st, dict) and st.get("semantic_ok") is False)
    layers = payload.get("layers") or {}
    l1_available = bool((layers.get("L1_事实层") or {}).get("available"))
    n_l1_rows = len((layers.get("L1_事实层") or {}).get("rows") or [])
    n_l2_views = int(((layers.get("L2_机构观点层") or {}).get("views") or {}).get("n") or 0)
    s8 = next((st for st in steps if isinstance(st, dict) and st.get("step") == "S8_grounded_qa"), None)
    s8_data = ((s8 or {}).get("envelope") or {}).get("data") or {}
    s8_status = s8_data.get("status")
    s8_ok = (s8 or {}).get("semantic_ok")
    n_s8_values = len(s8_data.get("values") or {}) if isinstance(s8_data, dict) else 0
    if run_ok is False:
        status, reason = "rejected", "下游研究明确返回失败/拒绝（run_ok=false）"
    elif s8_status in ("out_of_scope", "refused", "rejected", "unmapped", "no_registry_identity"):
        # The downstream system REFUSED the question; this is not a partial study.
        status, reason = "refused", f"下游明确拒答/越界（status={s8_status}）"
    elif s8 is None:
        status, reason = "partial", "缺少 S8 接地问答步骤，无法确认研究有效性"
    elif s8_ok is False:
        status, reason = "partial", "下游 S8 接地问答语义失败"
    elif n_steps_failed:
        status, reason = "partial", f"下游研究有 {n_steps_failed} 个步骤语义失败"
    elif (s8_ok is True and s8_status == "answered" and run_ok is True
          and (n_evidence or 0) >= 1 and (n_l1_rows > 0 or n_s8_values > 0)):
        status, reason = "ok_valid", "下游 S8 已接地作答（answered）并有事实值/事实行"
    elif s8_ok is True and s8_status == "answered" and run_ok is True:
        status, reason = "insufficient_data", "下游回答缺少 L1 事实行（不能仅凭观点行判成功）"
    elif s8_ok is True and s8_status == "answered" and (n_evidence or 0) == 0:
        status, reason = "insufficient_data", "S8 声称作答但 evidence_index 为空（仅有观点/空结果）"
    elif (n_evidence or 0) == 0:
        status, reason = "insufficient_data", "下游研究完成但证据行数为 0（数据不足）"
    else:
        status, reason = "partial", "结构化结果字段不完整，无法确认研究有效性"
    return {"semantic_status": status, "run_ok": run_ok, "n_evidence_rows": n_evidence,
            "n_steps_failed": n_steps_failed, "l1_available": l1_available,
            "n_l1_rows": n_l1_rows, "n_l2_views": n_l2_views, "s8_status": s8_status,
            "report_path": str(report_path) if report_path else None, "reason": reason}


@dataclass
class IAEnvironment:
    path: Path
    cli: Path
    python: str
    exists: bool
    has_cli: bool
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"path": str(self.path), "cli": str(self.cli), "python": self.python,
                "exists": self.exists, "has_cli": self.has_cli, "notes": self.notes}


class IAAdapter:
    def __init__(self, ia_path: str, python: str | None = None):
        self.path = Path(ia_path).expanduser().resolve()
        self.cli = self.path / "ia_cli.py"
        self.python = python or self._detect_python()
        self.env = self.check()

    def _detect_python(self) -> str:
        candidates = [self.path / ".venv" / "bin" / "python", Path("/usr/bin/python3"), Path(shutil.which("python3") or "")]
        for c in candidates:
            if c and Path(c).exists():
                return str(c)
        return sys.executable

    def check(self) -> IAEnvironment:
        notes: list[str] = []
        exists = self.path.exists()
        has_cli = self.cli.exists()
        if not exists:
            notes.append(f"investment-agent 路径不存在: {self.path}（可通过 --ia-path 指定）")
        if exists and not has_cli:
            notes.append("未找到 ia_cli.py；请确认路径指向 investment-agent 仓库根目录")
        if has_cli:
            try:
                out = subprocess.run([self.python, str(self.cli), "--help"], capture_output=True,
                                     text=True, timeout=60, cwd=str(self.path))
                if out.returncode != 0:
                    notes.append(f"ia_cli --help 返回 {out.returncode}: {out.stderr.strip()[:300]}")
                elif "research-run" not in out.stdout:
                    notes.append("ia_cli 未提供 research-run 子命令；接口可能需要更新")
            except Exception as exc:  # noqa: BLE001
                notes.append(f"无法执行 ia_cli: {type(exc).__name__}: {exc}")
        return IAEnvironment(self.path, self.cli, self.python, exists, has_cli, notes)

    # ------------------------------------------------------------------ commands
    def build_command(self, question: str, out_dir: str | Path, fanout: bool = False) -> list[str]:
        cmd = [self.python, str(self.cli), "research-run", "--question", question,
               "--out-dir", str(out_dir)]
        if fanout:
            cmd.append("--fanout")
        return cmd

    def run_task(self, question: str, out_dir: str | Path, timeout: int = 900,
                 fanout: bool = False) -> dict[str, Any]:
        if not self.env.has_cli:
            return {"status": "unavailable", "reason": "; ".join(self.env.notes) or "ia_cli.py missing"}
        out_dir = Path(out_dir)
        # Never reuse a previous run's report in the same out_dir: a crashed run
        # with rc!=0 could otherwise be judged from an old ok_valid artifact.
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd = self.build_command(question, out_dir, fanout=fanout)
        started = datetime.now(timezone.utc)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(self.path))
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            semantics = parse_research_artifact(out_dir, proc.stdout or "", min_mtime=started)
            # A process-level failure with no report is not a downstream refusal.
            if proc.returncode != 0 and not semantics.get("report_path"):
                semantics = {"semantic_status": "error",
                             "reason": f"下游进程执行失败 rc={proc.returncode}: "
                                       f"{(proc.stderr or proc.stdout or '')[-300:]}",
                             "run_ok": False, "n_evidence_rows": None,
                             "n_steps_failed": None, "report_path": None}
            # A zero exit code only proves the process ran. The task is "ok" only
            # when the downstream research artifact is semantically valid.
            overall = "ok" if (proc.returncode == 0 and semantics["semantic_status"] == "ok_valid") else "not_ok"
            return {
                "status": overall,
                "returncode": proc.returncode,
                "semantic_status": semantics["semantic_status"],
                "semantic_reason": semantics["reason"],
                "run_ok": semantics["run_ok"],
                "n_evidence_rows": semantics["n_evidence_rows"],
                "n_steps_failed": semantics["n_steps_failed"],
                "report_path": semantics["report_path"],
                "command": cmd,
                "out_dir": str(out_dir),
                "stdout_tail": (proc.stdout or "")[-4000:],
                "stderr_tail": (proc.stderr or "")[-2000:],
                "elapsed_s": round(elapsed, 2),
            }
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "command": cmd, "out_dir": str(out_dir), "timeout_s": timeout}
        except Exception as exc:  # noqa: BLE001
            return {"status": "error", "error": f"{type(exc).__name__}: {exc}", "command": cmd}

    # ------------------------------------------------------------------ persist
    def persist_result(self, store: Store, row: dict[str, Any], question: str,
                       res: dict[str, Any], target: Path) -> None:
        """Record the research run and its SEMANTIC status for one opportunity."""
        sem = res.get("semantic_status", "unknown")
        run_ok = res.get("status") == "ok" and sem == "ok_valid"
        existing = store.conn.execute(
            "SELECT task_id FROM research_tasks WHERE opportunity_id=? ORDER BY created_at LIMIT 1",
            (row["opportunity_id"],)).fetchone()
        task_id = existing["task_id"] if existing else f"RT-{row['opportunity_id']}"
        store.add_opportunity_event(
            row["opportunity_id"],
            "ia_research_run" if run_ok else "ia_research_not_completed",
            row["status"], row["status"],
            f"investment-agent: {sem} ({res.get('semantic_reason', '')})", run_id=None)
        store.upsert_research_task({
            "task_id": task_id, "opportunity_id": row["opportunity_id"],
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "target_system": "investment-agent",
            "payload": {"question": question, "result": res},
            "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "export_path": str(target),
            "status": "completed" if run_ok else f"not_completed:{sem if sem not in ('ok_valid','unknown') else res.get('status','unknown')}",
        })

    # -------------------------------------------------------------------- queue
    def run_queue(self, store: Store, records: list[dict[str, Any]], limit: int = 3,
                  out_dir: str | Path | None = None) -> list[dict[str, Any]]:
        """Run the deep-research CLI for the highest-priority opportunities.

        Only ``deep_research``/``watch`` records are eligible. Results are stored
        back on the research task row (never inside the investment-agent repo).
        """
        from .exporter import _json_field

        base = Path(out_dir) if out_dir else (Path.cwd() / "exports" / "ia_runs")
        results = []
        eligible = [r for r in records if r["status"] in ("deep_research", "watch")]
        eligible.sort(key=lambda r: -(r.get("score") or 0))
        from .exporter import build_research_question

        for row in eligible[:limit]:
            question = build_research_question(row)
            target = base / row["opportunity_id"]
            res = self.run_task(question, target)
            res["opportunity_id"] = row["opportunity_id"]
            results.append(res)
            self.persist_result(store, row, question, res, target)
        return results

    # ---------------------------------------------------------------- questions
    def export_question_patch(self, records: list[dict[str, Any]], path: str | Path) -> str:
        """Produce an append-only proposal for investment-agent's research questions.

        The existing ``config/research_questions.json`` belongs to the
        investment-agent charter and must not be overwritten by this project.
        This file is a merge proposal: ``append`` contains new question objects
        in the same shape (id/text/primary_layer/draws/surface).
        """
        from .exporter import _json_field

        append = []
        for row in records:
            disc = _json_field(row, "discovery_json", {})
            append.append({
                "id": f"GOE-{row['opportunity_id']}",
                "text": disc.get("hypothesis") or row.get("title", ""),
                "primary_layer": "AI推断",
                "draws": ["客观事实", "历史统计"],
                "surface": f"goe opportunity {row['opportunity_id']} (score {row.get('score'):.2f}, "
                           f"{row.get('archetype')}, {row.get('horizon')})",
            })
        payload = {
            "schema_version": "1.0",
            "source": "global-opportunity-engine",
            "merge_mode": "append",
            "target_file": "config/research_questions.json",
            "note": "Proposal only. Copy into the investment-agent repository manually (or via its own tooling).",
            "append": append,
        }
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(p)
