"""Command line interface (``goe``).

Commands
--------
    goe doctor                 environment, config, data coverage, provider health
    goe ingest                 backfill / incremental data download
    goe scan                   full pipeline (ingest -> ... -> reports -> handoff)
    goe opp list|show|status   inspect and update the opportunity pipeline
    goe handoff                build / run research tasks for investment-agent
    goe replay                 point-in-time historical validation
    goe export                 re-export the last pipeline artifacts
    goe web                    local read-only dashboard
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__, project_root
from .config import exports_dir
from .config import (
    load_curves,
    load_macro,
    load_positioning,
    load_sources,
    load_universe,
    load_yaml_config,
)
from .db import Store, default_db_path


# --------------------------------------------------------------------- helpers
def _print_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def _store(args: argparse.Namespace) -> Store:
    return Store(args.db or default_db_path())


# ------------------------------------------------------------------------ doctor
def cmd_doctor(args: argparse.Namespace) -> int:
    from .ingest import Ingestor

    checks: list[dict[str, Any]] = []

    def add(name: str, status: str, detail: str = "") -> None:
        checks.append({"check": name, "status": status, "detail": detail})

    add("python", "ok", f"{platform.python_version()} ({sys.executable})")
    add("platform", "ok", f"{platform.system()} {platform.release()} {platform.machine()}")
    try:
        import pandas, numpy, yfinance  # noqa: F401
        add("core_packages", "ok", "pandas/numpy/yfinance available")
    except Exception as exc:  # noqa: BLE001
        add("core_packages", "fail", str(exc))
    try:
        u = load_universe(); c = load_curves(); m = load_macro(); p = load_positioning(); s = load_sources()
        add("config", "ok", f"{len(u.instruments)} instruments, {len(c)} curves, {len(m)} macro, "
                            f"{len(p)} positioning, {len(s)} sources")
    except Exception as exc:  # noqa: BLE001
        add("config", "fail", f"{type(exc).__name__}: {exc}")
        u = c = m = p = s = None
    store = _store(args)
    try:
        n_prices = store.scalar("SELECT COUNT(*) FROM prices") or 0
        n_inst = store.scalar("SELECT COUNT(DISTINCT instrument_id) FROM prices") or 0
        last = store.scalar("SELECT MAX(date) FROM prices")
        n_ind = store.scalar("SELECT COUNT(*) FROM indicators") or 0
        n_series = store.scalar("SELECT COUNT(DISTINCT series_id) FROM indicators") or 0
        configured = len(load_universe().instruments)
        if n_prices:
            missing = sorted(set(load_universe().instruments) - set(store.instrument_ids()))
            add("database", "ok" if not missing else "warn",
                f"{n_prices} price rows / {n_inst} of {configured} configured instruments, last {last}; "
                f"{n_ind} indicator rows / {n_series} series"
                + (f"; missing prices: {', '.join(missing[:8])}" if missing else ""))
        else:
            add("database", "warn", "no price data yet — run `goe ingest --mode backfill`")
    except Exception as exc:  # noqa: BLE001
        add("database", "fail", str(exc))
    # provider availability
    try:
        providers = Ingestor(store).price_providers
        add("price_providers", "ok", ", ".join(sorted(providers)) or "none")
        ind = Ingestor(store).indicator_providers
        expected = {"treasury_us", "mof_japan", "ecb", "bls", "bis", "eurostat", "cftc",
                    "akshare_cn_bond", "shiller"}
        missing = expected - set(ind)
        add("indicator_providers", "ok" if not missing else "warn",
            f"available: {', '.join(sorted(ind))}; missing: {', '.join(sorted(missing)) or '-'}")
    except Exception as exc:  # noqa: BLE001
        add("providers", "fail", str(exc))
    # last scan
    try:
        row = store.conn.execute(
            "SELECT scan_id, as_of, status, finished_at FROM scan_runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        add("last_scan", "ok" if row else "warn",
            f"{dict(row)}" if row else "no scan yet — run `goe scan`")
        n_opp = store.scalar("SELECT COUNT(*) FROM opportunities") or 0
        add("pipeline", "ok", f"{n_opp} opportunities in store")
    except Exception as exc:  # noqa: BLE001
        add("pipeline", "fail", str(exc))
    # investment-agent
    ia_path = args.ia_path or os.environ.get("GOE_IA_PATH") or str(Path.home() / "investment-agent-dev")
    try:
        from .integration.ia_adapter import IAAdapter

        env = IAAdapter(ia_path).env
        add("investment_agent", "ok" if env.has_cli else "warn",
            f"{env.cli} via {env.python}" + (f" — {'; '.join(env.notes)}" if env.notes else ""))
    except Exception as exc:  # noqa: BLE001
        add("investment_agent", "warn", str(exc))
    try:
        from .events import EventCalendar

        cal = EventCalendar.load()
        nxt = cal.upcoming(str(store.scalar("SELECT MAX(date) FROM prices") or ""), within_days=60)
        add("event_calendar", "ok" if cal.events else "warn",
            f"{len(cal.events)} events; {len(nxt)} within 60 days"
            + ("" if cal.events else " — run `goe events --check` after populating config/events.yaml"))
    except Exception as exc:  # noqa: BLE001
        add("event_calendar", "warn", str(exc))
    # GitHub (informational only: publishing is a separate, explicit step)
    add("git", "ok" if shutil.which("git") else "warn", shutil.which("git") or "git not found")
    add("gh_cli", "ok" if shutil.which("gh") else "warn", shutil.which("gh") or "gh not installed (API/SSH only)")
    out = {"version": __version__, "db": str(store.path), "checks": checks}
    after = candidate_price_fingerprints(store)
    out["research_updates"] = notify_price_changes(store, before, after)
    if args.json:
        _print_json(out)
    else:
        print(f"Global Opportunity Engine {__version__} — doctor\n")
        for c in checks:
            icon = {"ok": "✓", "warn": "!", "fail": "✗"}.get(c["status"], "?")
            print(f"  [{icon}] {c['check']}: {c['detail']}")
        print(f"\nDB: {store.path}")
    store.close()
    return 0 if all(c["status"] != "fail" for c in checks) else 1


# ------------------------------------------------------------------------ ingest
def cmd_ingest(args: argparse.Namespace) -> int:
    from .ingest import Ingestor

    from .research_updates import candidate_price_fingerprints, notify_price_changes
    store = _store(args)
    ing = Ingestor(store)
    ing.register_metadata()
    before = candidate_price_fingerprints(store)
    out: dict[str, Any] = {}
    if not args.indicators_only:
        out["prices"] = ing.ingest_prices(mode=args.mode).to_dict()
    if not args.prices_only:
        try:
            out["indicators"] = ing.ingest_indicators(mode=args.mode).to_dict()
        except Exception as exc:  # noqa: BLE001
            out["indicators_error"] = f"{type(exc).__name__}: {exc}"
    after = candidate_price_fingerprints(store)
    out["research_updates"] = notify_price_changes(store, before, after)
    if args.json:
        _print_json(out)
    else:
        for k, v in out.items():
            print(f"{k}: {v}")
    store.close()
    return 0 if not any(k.endswith("_error") for k in out) else 1


# -------------------------------------------------------------------------- scan
def cmd_scan(args: argparse.Namespace) -> int:
    from .pipeline import run_scan
    from .readiness import ScanBlockedError

    store = _store(args)
    try:
        res = run_scan(
            store, as_of=args.as_of, ingest=not args.no_ingest, ingest_mode=args.ingest_mode,
            out_dir=args.out, export=not args.no_export, run_ia=args.handoff,
            ia_path=args.ia_path, max_candidates=args.max_candidates,
        )
    except ScanBlockedError as exc:
        msg = {"status": "blocked_data", "error": str(exc)}
        if args.json:
            _print_json(msg)
        else:
            print(f"SCAN BLOCKED: {exc}", file=sys.stderr)
        return 2
    finally:
        store.close()
    if args.json:
        _print_json({"scan_id": res.scan_id, "as_of": res.as_of, "stats": res.stats,
                     "reports": res.report_paths, "exports": res.export_paths})
    else:
        print(f"scan {res.scan_id} as_of={res.as_of}")
        st = res.stats
        print(f"  instruments={st.get('n_instruments')} anomalies={st.get('anomalies', {}).get('n')}")
        txs = st.get("transmissions", {})
        print(f"  transmissions={txs.get('n_activated')} by_status={txs.get('by_status')}")
        print(f"  opportunities={st.get('opportunities')}")
        print(f"  report: {res.report_paths.get('markdown')}")
        if res.export_paths.get("pipeline"):
            print(f"  pipeline export: {res.export_paths['pipeline']}")
    return 0


# --------------------------------------------------------------------- pipeline
def cmd_opp(args: argparse.Namespace) -> int:
    store = _store(args)
    if args.action == "list":
        df = store.opportunities(status=args.status, limit=args.limit)
        if df.empty:
            print("no opportunities")
            return 0
        if args.json:
            _print_json(df.to_dict("records"))
        else:
            cols = ["opportunity_id", "status", "score", "archetype", "market", "horizon", "title"]
            for r in df[cols].itertuples(index=False):
                print(f"{r.opportunity_id}  {r.score:.2f}  {r.status:<13} {r.market:<5} "
                      f"{r.archetype:<30} {r.title[:60]}")
        return 0
    if args.action == "show":
        row = store.conn.execute("SELECT * FROM opportunities WHERE opportunity_id=?", (args.id,)).fetchone()
        if not row:
            print(f"not found: {args.id}", file=sys.stderr)
            return 2
        rec = dict(row)
        events = store.opportunity_events(args.id).to_dict("records")
        if args.json:
            _print_json({"opportunity": rec, "events": events})
        else:
            from .reports import render_opportunity

            print(render_opportunity(rec))
            print("事件历史：")
            for e in events:
                print(f"  {e['at']} {e['event_type']}: {e.get('from_status')} -> {e.get('to_status')} {e.get('note','')}")
        return 0
    if args.action == "reopen":
        if not args.id:
            print("--id required for reopen")
            return 2
        orch.reopen(args.id, args.reason or "new evidence arrived")
        print(f"reopened={args.id}")
        return 0
    if args.action == "retry":
        if not args.id:
            print("--id required for retry")
            return 2
        orch.retry(args.id)
        print(f"retry_ready={args.id}")
        return 0
    if args.action == "status":
        source = "auto" if getattr(args, "auto", False) else "manual"
        ok = store.set_opportunity_status(args.id, args.set, args.reason or "manual update",
                                          source=source)
        print(f"{'updated' if ok else 'no change'} {args.id} (source={source})")
        return 0 if ok else 1
    if args.action == "events":
        df = store.opportunity_events(args.id)
        _print_json(df.to_dict("records"))
        return 0
    return 2


# ----------------------------------------------------------------------- handoff
def cmd_handoff(args: argparse.Namespace) -> int:
    from .integration.exporter import build_research_question
    from .integration.ia_adapter import IAAdapter

    store = _store(args)
    adapter = IAAdapter(args.ia_path, python=args.ia_python)
    exit_code = 0
    env = adapter.env
    print(f"investment-agent: {env.path} exists={env.exists} cli={env.has_cli} python={env.python}")
    for n in env.notes:
        print("  ! " + n)
    rows = store.opportunities(limit=500)
    if rows.empty:
        print("no opportunities to hand off")
        return 1
    eligible = rows[rows["status"].isin(["deep_research", "watch"])].sort_values("score", ascending=False)
    if eligible.empty:
        print("no deep_research/watch opportunities")
        return 1
    targets = eligible.head(args.limit).to_dict("records")
    if args.question_patch:
        path = adapter.export_question_patch(targets, args.question_patch)
        print(f"wrote question merge proposal: {path}")
    for row in targets:
        q = build_research_question(row)
        if args.dry_run:
            print(f"\n--- {row['opportunity_id']} (dry run) ---\n{q}\n")
            continue
        res = adapter.run_task(q, Path(args.out_dir) / row["opportunity_id"], timeout=args.timeout)
        adapter.persist_result(store, row, q, res, Path(args.out_dir) / row["opportunity_id"])
        print(f"{row['opportunity_id']}: {res.get('status')} rc={res.get('returncode')} "
              f"semantic={res.get('semantic_status')} elapsed={res.get('elapsed_s')} "
              f"out={res.get('out_dir')}")
        if res.get("status") != "ok" or res.get("semantic_status") != "ok_valid":
            exit_code = 2
            print((res.get("semantic_reason") or res.get("stderr_tail") or res.get("error") or "")[:1000])
    return exit_code


def cmd_triage(args: argparse.Namespace) -> int:
    """Research Discovery V2: structured research candidates (not a trade)."""
    import json as _json
    from .research_triage import run_triage

    store = _store(args)
    as_of = args.as_of or store.scalar("SELECT MAX(date) FROM prices")
    rows = run_triage(store, as_of=as_of, max_candidates=args.limit)
    for r in rows:
        store.upsert_research_candidate(r.to_dict(), status="intelligence" if r.priority_tier == "intelligence" else "active")
    out = Path(args.out) if args.out else (project_root() / "exports")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"research_candidates_{as_of}.json"
    payload = {"schema": "research-candidates/v2", "as_of": as_of,
               "candidates": [r.to_dict() for r in rows],
               "note": "Research questions, not investment conclusions; V2 triage does not replace B."}
    path.write_text(_json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"triage as_of={as_of} candidates={len(rows)} out={path}")
    for r in rows:
        print(f"  {r.research_id} tier={r.priority_tier} rank={r.priority_rank} "
              f"{','.join(r.instruments)} gap={r.materiality.get('gap_score')} cost={r.research_cost['hours']}h")
    if getattr(args, "handoff", False):
        from .integration.ia_adapter import IAAdapter
        from .integration.research_handoff import (eligible_for_handoff, handoff_v2,
                                                   persist_v2_result)
        eligible = eligible_for_handoff(rows)
        if not eligible:
            print("no eligible research candidate (tier A/B/C with evidence_ok); "
                  "intelligence is retained in A and not handed to B")
            return 3
        cand = eligible[0]
        target = Path(args.ia_out or "exports/research_v2_ia") / cand.research_id
        adapter = IAAdapter(args.ia_path or str(Path.home() / "investment-agent-dev"))
        res = handoff_v2(adapter, cand.to_dict(), target.parent, timeout=args.ia_timeout)
        persist_v2_result(store, cand.to_dict(), res, target)
        print(f"handoff {cand.research_id}: {res.get('status')} semantic={res.get('semantic_status')}")
        return 0 if res.get("status") == "ok" else 2
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    """Create a freeze manifest only from machine-verifiable test evidence."""
    from .release import build_manifest, run_test_proof

    store = _store(args)
    if args.run_tests:
        proof = run_test_proof()
        args.proof = proof["proof_path"]
    if not args.proof:
        raise SystemExit("--proof is required unless --run-tests is used")
    manifest = build_manifest(store, proof_path=args.proof, out_dir=args.out, notes=args.notes)
    print(f"release manifest: {manifest['path']}")
    print(f"commit={manifest['git_commit']} tests={manifest['test_evidence']['passed']} "
          f"scan={manifest['scan']['scan_id']}")
    return 0


def cmd_discovery(args: argparse.Namespace) -> int:
    import json as _json
    from .discovery import qualify
    doc = _json.loads(Path(args.artifact).read_text(encoding="utf-8"))
    rows = [qualify(c) for c in doc.get("candidates", [])]
    out = {"as_of": doc.get("as_of"), "rows": rows,
           "counts": {k: sum(1 for r in rows if r["classification"] == k)
                      for k in ("RESEARCH_READY", "EVIDENCE_TO_COLLECT", "INTELLIGENCE_ONLY", "DATA_ARTIFACT")}}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(_json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(_json.dumps(out["counts"], ensure_ascii=False))
    return 0


def cmd_intel(args: argparse.Namespace) -> int:
    import json as _json
    from .investment_intel import analyze
    f = _json.loads(Path(args.finding).read_text(encoding="utf-8"))
    out = analyze(f)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(_json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"expectations={out['market_expectations']['status']} "
          f"mispricing={out['expectation_gap']['status']}")
    return 0


def cmd_research(args: argparse.Namespace) -> int:
    """Generalized autonomous research entry: run / next / status."""
    from .research_orchestrator import (ResearchOrchestrator, case_nikkei, case_dxy,
                                        case_silver)
    store = Store(args.db or str(project_root() / "data" / "goe.db"))
    orch = ResearchOrchestrator(store)
    cases = {"nikkei": case_nikkei, "dxy": case_dxy, "silver": case_silver}
    if args.action == "reopen":
        if not args.id:
            print("--id required for reopen")
            return 2
        orch.reopen(args.id, args.reason or "new evidence arrived")
        print(f"reopened={args.id}")
        return 0
    if args.action == "retry":
        if not args.id:
            print("--id required for retry")
            return 2
        orch.retry(args.id)
        print(f"retry_ready={args.id}")
        return 0
    if args.action == "status":
        for r in orch.status():
            print(f"{r['research_id']} {r['asset_class']} state={r['workflow']} "
                  f"findings={r['findings']} latest={r['latest_finding']} "
                  f"updates={r['open_updates']} last_update={r['latest_update']}")
        return 0
    if args.action in ("run", "next"):
        if args.id:
            row = store.conn.execute("SELECT payload_json FROM research_v2_candidates WHERE research_id=?",
                                     (args.id,)).fetchone()
            if not row:
                print("candidate not found")
                return 1
            import json as _json
            c = _json.loads(row["payload_json"])
            spec = orch._spec_from_candidate(c)
        elif args.action == "next" or args.case == "next":
            spec = orch.next_case()
            if spec is None:
                print("no research case available")
                return 1
        elif args.case == "all":
            findings = []
            for name in ("nikkei", "dxy", "silver"):
                spec = cases[name]()
                orch.register(spec)
                f = orch.run(spec)
                findings.append(f)
                print(f"{name} {f.status} {f.finding_id}")
            print(f"cases={len(findings)}")
            return 0
        else:
            spec = cases[args.case]()
            orch.register(spec)
        f = orch.run(spec)
        print(f"finding={f.finding_id} status={f.status} event={f.event_date}")
        for line in f.learned:
            print("  -", line)
        return 0
    return 2


def cmd_research_case(args: argparse.Namespace) -> int:
    """Execute a real research case; never a plan-only dossier."""
    from .research_exec import execute_nikkei_case
    if args.case != "nikkei":
        print(f"unknown research case: {args.case}")
        return 2
    store = Store(args.db or str(project_root() / "data" / "goe.db"))
    finding = execute_nikkei_case(store, as_of=args.as_of, out_dir=args.out)
    print(f"finding={finding.finding_id} status={finding.status}")
    print(f"event={finding.event_date} evidence_sha256={finding.input_sha256}")
    for line in finding.learned:
        print(f"  - {line}")
    print(f"artifact={Path(args.out) / args.as_of / 'N225' / 'findings.md'}")
    return 0


def cmd_dossier(args: argparse.Namespace) -> int:
    """Generate source-bound Research Dossiers from a frozen candidate artifact."""
    import json as _json
    from .dossier import build_dossier, write_dossier

    artifact = Path(args.artifact) if args.artifact else (
        project_root() / "evaluation" / "v2_candidates_20_2026-11-13.json")
    try:
        artifact_ref = artifact.resolve().relative_to(project_root().resolve()).as_posix()
    except Exception:
        artifact_ref = str(artifact)
    doc = _json.loads(artifact.read_text(encoding="utf-8"))
    scan_meta = {}
    report_json = project_root() / "reports" / f"scan_{doc.get('as_of')}.json"
    if report_json.exists():
        try:
            scan_meta = _json.loads(report_json.read_text(encoding="utf-8")).get("meta") or {}
        except Exception:
            scan_meta = {}
    wanted = set(args.id or [])
    rows = []
    for c in doc.get("candidates") or []:
        if wanted and c.get("research_id") not in wanted:
            continue
        if not wanted and not args.all and c.get("research_queue") not in ("research", "watch"):
            continue
        if c.get("research_worthiness") == "high":
            label = "CASE_A_RESEARCH_WORTHY"
        elif float((c.get("materiality") or {}).get("gap_score") or 0.0) == 0.0:
            label = "CASE_B_NO_EXPLANATORY_GAP"
        else:
            label = "CASE_C_EVIDENCE_GAP"
        d = build_dossier(c, artifact_path=artifact_ref, scan_meta=scan_meta, case_label=label)
        paths = write_dossier(d, args.out)
        rows.append((d["dossier_id"], paths["markdown"]))
    for did, path in rows:
        print(f"{did} -> {path}")
    print(f"dossiers={len(rows)} artifact={artifact}")
    return 0 if rows else 1


def cmd_verify_release(args: argparse.Namespace) -> int:
    """Standalone, portable proof verification (safe on a fresh clone)."""
    from .release import ReleaseError, verify_test_proof

    try:
        proof = verify_test_proof(args.proof, cwd=".", rerun=not args.no_rerun)
    except ReleaseError as exc:
        print(f"RELEASE PROOF REJECTED: {exc}")
        return 1
    print(json.dumps({
        "status": "accepted",
        "commit": proof.get("git_commit"),
        "category": proof.get("category"),
        "passed": proof.get("passed"),
        "required": proof.get("required"),
        "executed": proof.get("executed"),
        "rerun": proof.get("rerun"),
    }, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------- export
def cmd_export(args: argparse.Namespace) -> int:
    from .integration.exporter import export_all

    store = _store(args)
    df = store.opportunities(limit=1000)
    if df.empty:
        print("no opportunities to export")
        return 1
    records = df.to_dict("records")
    meta = {
        "as_of": store.scalar("SELECT MAX(date) FROM prices"),
        "engine_version": __version__,
        "scan_id": store.scalar("SELECT scan_id FROM scan_runs ORDER BY started_at DESC LIMIT 1") or "",
        "config_hash": store.config_fingerprint(),
        "data_hash": store.data_fingerprint(store.scalar("SELECT MAX(date) FROM prices")),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    paths = export_all(store, records, meta, base_dir=Path(args.out) if args.out else exports_dir())
    _print_json(paths)
    return 0


# ---------------------------------------------------------------------- events
def cmd_events(args: argparse.Namespace) -> int:
    from .config import load_curves, load_macro, load_themes
    from .events import EventCalendar

    cal = EventCalendar.load()
    if not args.check:
        rows = [{"id": e.id, "date": e.date, "region": e.region, "type": e.type,
                 "title": e.title, "verified": e.verified, "affects": e.affects}
                for e in cal.events]
        _print_json(rows)
        return 0
    ids = set(load_universe().instruments) | set(load_macro())
    for cid, cdef in load_curves().items():
        ids.add(cid)
        ids.update(f"{cid}:{t}" for t in cdef.tenors)
    problems = []
    seen = set()
    for e in cal.events:
        if e.id in seen:
            problems.append(f"duplicate id {e.id}")
        seen.add(e.id)
        for a in e.affects:
            if a not in ids:
                problems.append(f"{e.id}: unknown affects id {a}")
        try:
            datetime.strptime(e.date, "%Y-%m-%d")
        except Exception:
            problems.append(f"{e.id}: bad date {e.date}")
    n_verified = sum(1 for e in cal.events if e.verified)
    out = {"events": len(cal.events), "verified": n_verified,
           "unverified": [e.id for e in cal.events if not e.verified],
           "first": cal.events[0].date if cal.events else None,
           "last": cal.events[-1].date if cal.events else None,
           "problems": problems, "ok": not problems}
    after = candidate_price_fingerprints(store)
    out["research_updates"] = notify_price_changes(store, before, after)
    if args.json:
        _print_json(out)
    else:
        print(f"events={out['events']} verified={out['verified']} "
              f"range={out['first']}..{out['last']}")
        if out["unverified"]:
            print("unverified (excluded from catalyst scoring unless reviewed): "
                  + ", ".join(out["unverified"]))
        if problems:
            print("PROBLEMS:")
            for p in problems[:20]:
                print("  - " + p)
        else:
            print("all referenced ids and dates are valid")
    return 0 if not problems else 1


# ------------------------------------------------------------------------- web
def cmd_web(args: argparse.Namespace) -> int:
    from .web.app import serve

    serve(db_path=args.db or default_db_path(), host=args.host, port=args.port)
    return 0


# -------------------------------------------------------------------- argparse
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="goe", description="Global Investment Opportunity Discovery Engine")
    p.add_argument("--version", action="version", version=f"goe {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor", help="环境/配置/数据/依赖体检")
    d.add_argument("--db")
    d.add_argument("--ia-path")
    d.add_argument("--json", action="store_true")
    d.set_defaults(func=cmd_doctor)

    i = sub.add_parser("ingest", help="数据下载（backfill / incremental）")
    i.add_argument("--db")
    i.add_argument("--mode", choices=["backfill", "incremental"], default="incremental")
    i.add_argument("--prices-only", action="store_true")
    i.add_argument("--indicators-only", action="store_true")
    i.add_argument("--json", action="store_true")
    i.set_defaults(func=cmd_ingest)

    s = sub.add_parser("scan", help="运行完整扫描管线")
    s.add_argument("--db")
    s.add_argument("--as-of")
    s.add_argument("--no-ingest", action="store_true")
    s.add_argument("--ingest-mode", choices=["backfill", "incremental"], default="incremental")
    s.add_argument("--out", help="报告输出目录（默认 reports/）")
    s.add_argument("--no-export", action="store_true")
    s.add_argument("--handoff", action="store_true", help="扫描后自动为 top 机会运行 investment-agent research-run")
    s.add_argument("--ia-path")
    s.add_argument("--max-candidates", type=int, default=25)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_scan)

    o = sub.add_parser("opp", help="机会候选池操作")
    o.add_argument("action", choices=["list", "show", "status", "events"])
    o.add_argument("id", nargs="?")
    o.add_argument("--db")
    o.add_argument("--status")
    o.add_argument("--limit", type=int, default=50)
    o.add_argument("--set", help="status: new/watch/deep_research/low_priority/excluded/archived")
    o.add_argument("--reason")
    o.add_argument("--auto", action="store_true", help="清除人工保护，交回自动评分")
    o.add_argument("--json", action="store_true")
    o.set_defaults(func=cmd_opp)

    h = sub.add_parser("handoff", help="把候选机会交给 investment-agent")
    h.add_argument("--db")
    h.add_argument("--ia-path", required=True)
    h.add_argument("--ia-python")
    h.add_argument("--limit", type=int, default=3)
    h.add_argument("--out-dir", default=str(exports_dir() / "ia_runs"))
    h.add_argument("--timeout", type=int, default=900)
    h.add_argument("--dry-run", action="store_true")
    h.add_argument("--question-patch", help="输出 research_questions 追加提案 JSON")
    h.set_defaults(func=cmd_handoff)

    t = sub.add_parser("triage", help="Research Discovery V2：生成结构化研究问题")
    t.add_argument("--db", default=None)
    t.add_argument("--as-of", default=None)
    t.add_argument("--out", default=None)
    t.add_argument("--limit", type=int, default=5)
    t.add_argument("--handoff", action="store_true", help="把最高优先级 V2 研究问题交给 investment-agent")
    t.add_argument("--ia-path", default=None)
    t.add_argument("--ia-out", default=None)
    t.add_argument("--ia-timeout", type=int, default=300)
    t.set_defaults(func=cmd_triage)

    dsc = sub.add_parser("discovery", help="Research Opportunity Qualification")
    dsc.add_argument("--artifact", default="evaluation/v2_candidates_20_2026-11-13.json")
    dsc.add_argument("--out", default="evaluation/discovery_qualification.json")
    dsc.set_defaults(func=cmd_discovery)

    intel = sub.add_parser("intel", help="证据门控投资情报")
    intel.add_argument("--finding", required=True)
    intel.add_argument("--out", default="evaluation/investment_intelligence.json")
    intel.set_defaults(func=cmd_intel)

    rsub = sub.add_parser("research", help="通用研究执行/调度")
    rsub.add_argument("action", choices=["run", "next", "status", "retry", "reopen"])
    rsub.add_argument("--id", default=None)
    rsub.add_argument("--reason", default=None)
    rsub.add_argument("--case", default="next", choices=["nikkei", "dxy", "silver", "all", "next"])
    rsub.add_argument("--db", default=None)
    rsub.set_defaults(func=cmd_research)

    rc = sub.add_parser("research-case", help="执行真实研究案例并产出 Finding")
    rc.add_argument("--case", default="nikkei")
    rc.add_argument("--as-of", default="2026-11-13")
    rc.add_argument("--out", default="research_results")
    rc.add_argument("--db", default=None)
    rc.set_defaults(func=cmd_research_case)

    d = sub.add_parser("dossier", help="生成可检查的 Research Dossier")
    d.add_argument("--artifact", default=None)
    d.add_argument("--out", default="research_dossiers")
    d.add_argument("--all", action="store_true")
    d.add_argument("--id", action="append")
    d.set_defaults(func=cmd_dossier)

    rel = sub.add_parser("release", help="用可验证测试证明冻结发布清单")
    rel.add_argument("--db", default=None)
    rel.add_argument("--proof", default=None)
    rel.add_argument("--run-tests", action="store_true")
    rel.add_argument("--out", default="audit/releases")
    rel.add_argument("--notes", default="")
    rel.set_defaults(func=cmd_release)

    rv = sub.add_parser("verify-release", help="校验测试证明能否在当前机器/提交上重放")
    rv.add_argument("--proof", required=True)
    rv.add_argument("--no-rerun", action="store_true", help="只做结构校验，不重新执行测试")
    rv.set_defaults(func=cmd_verify_release)

    e = sub.add_parser("export", help="重新导出最近机会管线的交接文件")
    e.add_argument("--db")
    e.add_argument("--out")
    e.set_defaults(func=cmd_export)

    r = sub.add_parser("replay", help="历史时点回放验证（无前视）")
    r.add_argument("--db")
    r.add_argument("--start")
    r.add_argument("--end")
    r.add_argument("--step", type=int, default=21)
    r.add_argument("--cases", action="store_true", help="运行预置历史案例检验")
    r.add_argument("--out")
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=cmd_replay)

    ev = sub.add_parser("events", help="事件日历查看/校验")
    ev.add_argument("--check", action="store_true", help="校验日期与引用的标的 id")
    ev.add_argument("--json", action="store_true")
    ev.set_defaults(func=cmd_events)

    w = sub.add_parser("web", help="本地只读仪表盘")
    w.add_argument("--db")
    w.add_argument("--host", default="127.0.0.1")
    w.add_argument("--port", type=int, default=8765)
    w.set_defaults(func=cmd_web)
    return p


def cmd_replay(args: argparse.Namespace) -> int:
    from .validation import run_case_validation, run_replay

    store = _store(args)
    if args.cases:
        out = run_case_validation(store, out_dir=args.out)
    else:
        out = run_replay(store, start=args.start, end=args.end, step=args.step, out_dir=args.out)
    after = candidate_price_fingerprints(store)
    out["research_updates"] = notify_price_changes(store, before, after)
    if args.json:
        _print_json(out)
    store.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
