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

from ..db import Store


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
        out_dir.mkdir(parents=True, exist_ok=True)
        cmd = self.build_command(question, out_dir, fanout=fanout)
        started = datetime.now(timezone.utc)
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(self.path))
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            return {
                "status": "ok" if proc.returncode == 0 else "failed",
                "returncode": proc.returncode,
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
            if res.get("status") == "ok":
                store.add_opportunity_event(row["opportunity_id"], "ia_research_run", row["status"],
                                            row["status"], f"investment-agent research-run 完成: {target}",
                                            run_id=None)
                store.upsert_research_task({
                    "task_id": f"RT-{row['opportunity_id']}",
                    "opportunity_id": row["opportunity_id"],
                    "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "target_system": "investment-agent",
                    "payload": {"question": question, "result": res},
                    "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "export_path": str(target), "status": "completed",
                })
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
