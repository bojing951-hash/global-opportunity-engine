#!/usr/bin/env python3
"""Materialize every research finding into a unique versioned artifact and relink DB.

Historical root-level finding files may be superseded; this script never rewrites
the root files. It reconstructs each DB payload under <asset>/<finding_id>/.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    conn = sqlite3.connect(ROOT / "data" / "goe.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT f.finding_id,f.research_id,f.status,f.payload_json,
                  c.instruments_json,c.as_of
           FROM research_v2_findings f
           JOIN research_v2_candidates c ON c.research_id=f.research_id""").fetchall()
    fixed = 0
    for r in rows:
        payload = json.loads(r["payload_json"] or "{}")
        instruments = json.loads(r["instruments_json"] or "[]")
        asset = str(instruments[0]) if instruments else str(payload.get("asset", "unknown"))
        out = ROOT / "research_results" / str(r["as_of"]) / asset / str(r["finding_id"])
        if (out / "finding.json").exists():
            continue  # never overwrite an existing versioned finding artifact
        out.mkdir(parents=True, exist_ok=True)
        (out / "finding.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
        learned = payload.get("learned") or []
        md = [f"# Research Finding — {asset}", "",
              f"- Finding: `{r['finding_id']}`",
              f"- Research: `{r['research_id']}`",
              f"- Status: {r['status']}", "", "## What we learned"]
        md += [f"- {x}" for x in learned]
        md += ["", "DISCOVERY VALUE: NOT VALIDATED"]
        (out / "findings.md").write_text("\n".join(md), encoding="utf-8")
        rel = str(out.relative_to(ROOT) / "finding.json")
        conn.execute("UPDATE research_v2_findings SET artifact_path=? WHERE finding_id=?",
                     (rel, r["finding_id"]))
        fixed += 1
    conn.commit()
    # Mark legacy root-level artifacts; versioned directories are authoritative.
    for d in sorted((ROOT / "research_results").glob("*/*")):
        if d.is_dir() and (d / "finding.json").exists() and not d.name.startswith("RF-"):
            (d / "LEGACY_ROOT.md").write_text(
                "Legacy root artifact. Authoritative findings are in the `RF-*` versioned\n"
                "subdirectories relinked in `research_v2_findings.artifact_path`.\n", encoding="utf-8")
    print(f"relinked={fixed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
