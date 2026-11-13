"""Local read-only dashboard (stdlib only, no build step).

Serves a single page that embeds the latest pipeline as JSON and filters it in
the browser by date, market, asset class, industry/archetype, status and free
text. Also exposes a small JSON API (``/api/opportunities`` etc.) so the page
and external tools use the same data.

Read-only by design: the dashboard never mutates the database or calls the
investment-agent. Research actions stay in the CLI (``goe handoff``).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..config import load_universe
from ..db import Store

PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Global Opportunity Engine — Opportunity Pipeline</title>
<style>
:root { --bg:#0f1115; --panel:#161a21; --line:#252b36; --text:#e8ecf3; --muted:#8b95a7;
        --accent:#5aa9ff; --good:#37c978; --warn:#f2b03d; --bad:#ef5b5b; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC",sans-serif; }
header { padding:22px 28px 10px; border-bottom:1px solid var(--line); }
h1 { margin:0 0 4px; font-size:19px; font-weight:650; letter-spacing:.2px; }
.sub { color:var(--muted); font-size:12.5px; }
.stats { display:flex; gap:18px; margin-top:12px; flex-wrap:wrap; }
.stat { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:8px 14px; min-width:110px; }
.stat b { display:block; font-size:19px; }
.stat span { color:var(--muted); font-size:11.5px; }
main { padding:18px 28px 60px; }
.filters { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:14px; align-items:center; }
select,input { background:var(--panel); color:var(--text); border:1px solid var(--line); border-radius:6px; padding:7px 9px; font-size:13px; }
input[type=search] { min-width:260px; }
table { width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--line); border-radius:8px; overflow:hidden; }
th,td { text-align:left; padding:9px 11px; border-bottom:1px solid var(--line); vertical-align:top; font-size:13px; }
th { color:var(--muted); font-weight:600; font-size:11.5px; text-transform:uppercase; letter-spacing:.4px; background:#12161d; }
tr:hover td { background:#1a1f28; cursor:pointer; }
.badge { display:inline-block; padding:1px 8px; border-radius:99px; font-size:11.5px; border:1px solid var(--line); }
.deep_research { color:var(--good); border-color:#245c3c; }
.watch { color:var(--warn); border-color:#5c4a1f; }
.low_priority,.new { color:var(--muted); }
.excluded,.expired,.invalidated { color:var(--bad); border-color:#5c2525; }
.score { font-variant-numeric:tabular-nums; font-weight:600; }
.detail { background:#12161d; }
.detail td { padding:16px 18px; }
.kv { display:grid; grid-template-columns:130px 1fr; gap:6px 14px; margin:0 0 12px; }
.kv dt { color:var(--muted); }
.kv dd { margin:0; }
.ev { margin:0; padding-left:18px; }
.ev li { margin:3px 0; }
h3 { font-size:14px; margin:14px 0 6px; color:var(--accent); }
footer { color:var(--muted); font-size:11.5px; padding:0 28px 40px; }
.mono { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; }
</style>
</head>
<body>
<header>
  <h1>Global Opportunity Engine — 投资机会研究队列</h1>
  <div class="sub" id="meta"></div>
  <div class="stats" id="stats"></div>
</header>
<main>
  <div class="filters">
    <select id="fStatus"><option value="">全部状态</option></select>
    <select id="fMarket"><option value="">全部市场</option></select>
    <select id="fAsset"><option value="">全部资产类别</option></select>
    <select id="fArch"><option value="">全部类型</option></select>
    <input id="fSearch" type="search" placeholder="搜索标题 / 标的 / 现象 / 机制…">
  </div>
  <table>
    <thead><tr><th>机会</th><th>状态</th><th>评分</th><th>市场</th><th>资产</th><th>周期</th><th>标题</th><th>首次发现</th></tr></thead>
    <tbody id="rows"></tbody>
  </table>
</main>
<footer id="foot"></footer>
<script>
const DATA = __DATA__;
const REGION = __REGION__;
const fmt = (x)=> x==null? "n/a" : Number(x).toFixed(3);
const esc = (s)=> String(s??"").replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
document.getElementById('meta').textContent =
  `as_of ${DATA.meta.as_of} · scan ${DATA.meta.scan_id} · engine ${DATA.meta.engine} · 数据截止 ${DATA.meta.data_last} · 生成 ${DATA.meta.generated_at}`;
const stats = [
  ['候选机会', DATA.opportunities.length],
  ['重点研究', DATA.opportunities.filter(o=>o.status==='deep_research').length],
  ['持续观察', DATA.opportunities.filter(o=>o.status==='watch').length],
  ['异常', DATA.anomalies.length],
  ['已激活机制', DATA.transmissions.length],
];
document.getElementById('stats').innerHTML = stats.map(([k,v])=>`<div class="stat"><b>${v}</b><span>${k}</span></div>`).join('');

function fill(id, values) {
  const el = document.getElementById(id);
  [...new Set(values.filter(Boolean))].sort().forEach(v=>{
    const o=document.createElement('option'); o.value=v; o.textContent= id==='fMarket' ? (REGION[v]||v) : v; el.appendChild(o);
  });
}
fill('fStatus', DATA.opportunities.map(o=>o.status));
fill('fMarket', DATA.opportunities.map(o=>o.market));
fill('fAsset', DATA.opportunities.map(o=>o.asset_class));
fill('fArch', DATA.opportunities.map(o=>o.archetype));

function detail(o) {
  const ev = (arr) => (arr||[]).map(e=>`<li><b>${esc(e.claim)}</b>：${esc(e.evidence)} <span class="mono">[${esc(e.source||'')} ${esc(e.as_of||'')}]</span></li>`).join('') || '<li>—</li>';
  return `<div class="kv">
    <dt>机会编号</dt><dd class="mono">${esc(o.opportunity_id)} · ${esc(o.fingerprint)}</dd>
    <dt>发现</dt><dd>${esc(o.discovery.what)}</dd>
    <dt>为什么现在</dt><dd>${esc(o.discovery.why_now)}</dd>
    <dt>待检验假设</dt><dd>${esc(o.discovery.hypothesis||'—')}</dd>
    <dt>传导链条</dt><dd>${(o.mechanism.chain||[]).map(esc).join(' → ')||'—'}</dd>
    <dt>机制置信度</dt><dd>${o.mechanism.confidence!=null?Number(o.mechanism.confidence).toFixed(2):'—'} · ${esc(o.mechanism.identification||'')}</dd>
    <dt>评分构成</dt><dd class="mono">${esc(JSON.stringify(o.score_breakdown))}</dd>
    <dt>标的</dt><dd>${(o.instruments||[]).map(i=>esc(i.name)+' ('+esc(i.id)+')').join('；')}</dd>
  </div>
  <h3>支持证据</h3><ul class="ev">${ev(o.evidence_for)}</ul>
  <h3>反对证据 / 替代解释</h3><ul class="ev">${ev(o.evidence_against)}</ul>
  <h3>需要深入研究</h3><ul class="ev">${(o.open_questions||[]).map(q=>`<li>${esc(q)}</li>`).join('')||'<li>—</li>'}</ul>
  <h3>失效条件</h3><div>${esc(o.invalidation||'—')}</div>
  <h3>研究问题（交给 investment-agent）</h3><div class="mono" style="white-space:pre-wrap">${esc(o.research_question||'—')}</div>`;
}

let expanded = null;
function render() {
  const st=document.getElementById('fStatus').value, mk=document.getElementById('fMarket').value,
        ac=document.getElementById('fAsset').value, ar=document.getElementById('fArch').value,
        q=document.getElementById('fSearch').value.toLowerCase();
  const rows = DATA.opportunities.filter(o=>
      (!st||o.status===st)&&(!mk||o.market===mk)&&(!ac||o.asset_class===ac)&&(!ar||o.archetype===ar)&&
      (!q || JSON.stringify(o).toLowerCase().includes(q)));
  const tb=document.getElementById('rows');
  tb.innerHTML = rows.map(o=>{
    const main=`<tr data-id="${esc(o.opportunity_id)}">
      <td class="mono">${esc(o.opportunity_id)}</td>
      <td><span class="badge ${esc(o.status)}">${esc(o.status)}</span></td>
      <td class="score">${fmt(o.score)}</td>
      <td>${esc(REGION[o.market]||o.market)}</td>
      <td>${esc(o.asset_class)}</td><td>${esc(o.horizon)}</td>
      <td>${esc(o.title)}</td><td>${esc(o.first_seen)}</td></tr>`;
    const det = expanded===o.opportunity_id ? `<tr class="detail"><td colspan="8">${detail(o)}</td></tr>`:'';
    return main+det;
  }).join('') || '<tr><td colspan="8" style="color:#8b95a7">没有匹配的候选机会。</td></tr>';
  tb.querySelectorAll('tr[data-id]').forEach(tr=>tr.addEventListener('click',()=>{
    const id=tr.dataset.id; expanded = expanded===id? null:id; render();
  }));
}
['fStatus','fMarket','fAsset','fArch','fSearch'].forEach(id=>document.getElementById(id).addEventListener('input',render));
document.getElementById('foot').textContent =
  `只读仪表盘 · 评分衡量研究优先级而非预期收益 · 数据来源与限制见报告文件 · 生成时间 ${new Date().toISOString()}`;
render();
</script>
</body>
</html>
"""


def _json_field(row: dict[str, Any], key: str, default: Any) -> Any:
    raw = row.get(key)
    if raw is None:
        return default
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return default
    return raw


def build_payload(store: Store) -> dict[str, Any]:
    from ..opportunities import REGION_CN

    opps_df = store.opportunities(limit=1000)
    opportunities = []
    for row in opps_df.to_dict("records"):
        from ..integration.exporter import opportunity_envelope

        meta = {
            "engine_version": "0.1.0",
            "scan_id": store.scalar("SELECT scan_id FROM scan_runs ORDER BY started_at DESC LIMIT 1") or "",
            "as_of": row["as_of"],
            "config_hash": "",
            "data_hash": "",
        }
        env = opportunity_envelope(store, row, meta)["opportunity"]
        opportunities.append(env)
    scan = store.conn.execute(
        "SELECT scan_id, as_of, status, finished_at FROM scan_runs ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    anomalies = store.conn.execute(
        "SELECT detector, family, instrument_id, direction, score, window FROM anomalies "
        "WHERE as_of=(SELECT MAX(as_of) FROM anomalies) ORDER BY score DESC LIMIT 200"
    ).fetchall()
    transmissions = store.conn.execute(
        "SELECT mechanism_id, title, confidence, status FROM transmissions "
        "WHERE as_of=(SELECT MAX(as_of) FROM transmissions) ORDER BY confidence DESC LIMIT 100"
    ).fetchall()
    return {
        "meta": {
            "as_of": (dict(scan)["as_of"] if scan else ""),
            "scan_id": (dict(scan)["scan_id"] if scan else ""),
            "engine": "0.1.0",
            "data_last": store.scalar("SELECT MAX(date) FROM prices") or "",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        },
        "region_names": REGION_CN,
        "opportunities": opportunities,
        "anomalies": [dict(r) for r in anomalies],
        "transmissions": [dict(r) for r in transmissions],
    }


def render_page(store: Store) -> str:
    from ..opportunities import REGION_CN

    payload = build_payload(store)
    return PAGE.replace("__DATA__", json.dumps(payload, ensure_ascii=False, default=str)) \
               .replace("__REGION__", json.dumps(REGION_CN, ensure_ascii=False))


def make_handler(db_path: str | Path):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:  # quieter logs
            return

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            store = Store(db_path)
            try:
                if path in ("/", "/index.html"):
                    self._send(200, render_page(store).encode("utf-8"), "text/html; charset=utf-8")
                elif path == "/api/opportunities":
                    q = parse_qs(parsed.query)
                    payload = build_payload(store)
                    items = payload["opportunities"]
                    if q.get("status"):
                        items = [o for o in items if o["status"] == q["status"][0]]
                    if q.get("market"):
                        items = [o for o in items if o["market"] == q["market"][0]]
                    if q.get("asset_class"):
                        items = [o for o in items if o["asset_class"] == q["asset_class"][0]]
                    self._send(200, json.dumps(items, ensure_ascii=False, default=str).encode(),
                               "application/json; charset=utf-8")
                elif path == "/api/health":
                    self._send(200, json.dumps({"ok": True,
                                                "rows": store.scalar("SELECT COUNT(*) FROM prices") or 0}).encode(),
                               "application/json; charset=utf-8")
                else:
                    self._send(404, b"not found", "text/plain; charset=utf-8")
            finally:
                store.close()

    return Handler


def serve(db_path: str | Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    st = Store(db_path)
    n = st.scalar("SELECT COUNT(*) FROM opportunities") or 0
    st.close()
    if n == 0:
        print("warning: no opportunities in the database yet; run `goe scan` first")
    server = ThreadingHTTPServer((host, port), make_handler(db_path))
    print(f"dashboard: http://{host}:{port} (read-only, Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
