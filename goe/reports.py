"""Report generation: Markdown research briefs, JSON exports and an HTML dashboard.

The report is deliberately organised around *why an opportunity entered the
pipeline*, not around a chronological news feed. Every number in the brief can
be traced back to a feature row, an anomaly row, or a transmission record.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .config import load_universe
from .db import Store
from .features import FeatureSet
from .opportunities import REGION_CN

KEY_INSTRUMENTS = [
    "US_EQ_SPY", "US_EQ_QQQ", "US_EQ_IWM", "CN_EQ_CSI300", "CN_EQ_SSE", "HK_EQ_HSI",
    "JP_EQ_N225", "EA_EQ_SX5E", "UK_EQ_FTSE", "WORLD_EQ_EEM",
    "US_FX_DXY", "GX_FX_EURUSD", "GX_FX_USDJPY", "CN_FX_USDCNY",
    "CM_MET_GC", "CM_MET_SI", "CM_MET_HG", "CM_ENE_CL", "CM_ENE_NG", "CM_AGR_ZS", "CM_AGR_ZC",
    "US_FI_TLT", "US_FI_IEF", "US_CR_HYG", "US_CR_LQD", "CR_BTC", "US_VOL_VIX", "US_VOL_MOVE",
]


def _pct(x: float, digits: int = 1) -> str:
    if x is None or not np.isfinite(x):
        return "n/a"
    return f"{x * 100:+.{digits}f}%"


def _num(x: float, digits: int = 2) -> str:
    if x is None or not np.isfinite(x):
        return "n/a"
    return f"{x:.{digits}f}"


def _name(entity_id: str, universe: dict[str, Any] | None = None) -> str:
    u = universe or load_universe().instruments
    spec = u.get(entity_id)
    return spec.name if spec else entity_id


def market_snapshot(fs: FeatureSet) -> pd.DataFrame:
    rows = []
    for iid in KEY_INSTRUMENTS:
        if iid not in fs.prices.columns:
            continue
        row = {"id": iid, "name": _name(iid)}
        for w in ("1w", "1m", "3m", "12m"):
            row[w] = fs.value(iid, "return", w)
        row["vol_3m"] = fs.value(iid, "ann_vol", "3m")
        row["dd_1y"] = fs.value(iid, "drawdown_252d")
        rows.append(row)
    return pd.DataFrame(rows)


def curve_snapshot(fs: FeatureSet) -> pd.DataFrame:
    rows = []
    for cid in fs.curve:
        row = {"curve": cid}
        for tenor in ("2Y", "10Y", "30Y"):
            row[f"{tenor}"] = fs.value(f"{cid}:{tenor}", "level", tenor)
        row["2s10s"] = fs.value(cid, "slope_2s10s")
        row["2s10s_1m_chg"] = fs.value(cid, "slope_2s10s_change_1m", "1m")
        rows.append(row)
    return pd.DataFrame(rows)


def macro_snapshot(fs: FeatureSet, store: Store | None = None) -> pd.DataFrame:
    rows = []
    for sid in sorted(set(fs.long.loc[fs.long.entity_kind == "macro", "entity_id"])):
        rows.append({
            "id": sid,
            "value": fs.value(sid, "value", "monthly") if fs.value(sid, "value", "monthly") == fs.value(sid, "value", "monthly") else fs.value(sid, "value", "quarterly"),
            "change_3p": fs.value(sid, "change_3p", "monthly") if fs.value(sid, "change_3p", "monthly") == fs.value(sid, "change_3p", "monthly") else fs.value(sid, "change_3p", "quarterly"),
            "z_3y": fs.value(sid, "z_3y", "monthly") if fs.value(sid, "z_3y", "monthly") == fs.value(sid, "z_3y", "monthly") else fs.value(sid, "z_3y", "quarterly"),
        })
    return pd.DataFrame(rows)


def render_anomaly_table(anomalies: pd.DataFrame, limit: int = 40) -> str:
    """Most significant anomalies from the last five calendar days.

    A single-day table would be nearly empty because exchanges close on
    different dates; five days captures the current information set while
    keeping the table focused.
    """
    if anomalies.empty:
        return "_本次扫描没有触发任何异常。_\n"
    dates = pd.to_datetime(anomalies["date"])
    recent = anomalies[dates >= (dates.max() - pd.Timedelta(days=5))]
    recent = recent.sort_values(["score", "date"], ascending=False).head(limit)
    lines = ["| 日期 | 资产/序列 | 家族 | 检测器 | 方向 | 强度 | 窗口 |", "|---|---|---|---|---|---|---|"]
    for r in recent.to_dict("records"):
        lines.append(f"| {r['date']} | {_name(r['entity_id'])} (`{r['entity_id']}`) | {r['family']} | "
                     f"{r['detector']} | {r['direction']} | {float(r['score']):.2f} | {r.get('window') or '-'} |")
    return "\n".join(lines) + "\n"


def render_opportunity(rec: dict[str, Any], detail: bool = True) -> str:
    """Structured opportunity profile (the OPP-XXXX format from the spec)."""
    d = rec
    lines = [f"### {d['opportunity_id']} — {d['title']}", ""]
    lines.append(f"- **状态**: `{d['status']}`" + (f"（{d['status_reason']}）" if d.get("status_reason") else ""))
    lines.append(f"- **评分**: {d['score']:.3f}（研究优先级，非预期收益）")
    lines.append(f"- **市场/资产类别**: {REGION_CN.get(d['market'], d['market'])} / {d['asset_class']}")
    lines.append(f"- **研究周期**: {d['horizon']}")
    lines.append(f"- **首次发现 / 最近更新**: {d['first_seen']} / {d['last_seen']}")
    instruments = json.loads(d["instruments_json"]) if isinstance(d.get("instruments_json"), str) else d.get("instruments", [])
    lines.append(f"- **标的**: " + "；".join(f"{i.get('name','')} (`{i.get('id','')}`)" for i in instruments))
    disc = json.loads(d["discovery_json"]) if isinstance(d.get("discovery_json"), str) else d.get("discovery", {})
    lines.append("")
    lines.append(f"**发现了什么**：{disc.get('what', '')}")
    lines.append("")
    lines.append(f"**为什么值得关注**：{disc.get('why_now', '')}")
    lines.append("")
    if disc.get("hypothesis"):
        lines.append(f"**待检验假设**：{disc['hypothesis']}")
        lines.append("")
    mech = json.loads(d["mechanism_json"]) if isinstance(d.get("mechanism_json"), str) else d.get("mechanism", {})
    chain = " → ".join(mech.get("chain", [])) or "（未提供）"
    lines.append(f"**宏观传导**：{chain}  ")
    lines.append(f"机制置信度 {mech.get('confidence', 0):.2f}；识别状态：{mech.get('identification', 'hypothesis')}")
    if mech.get("conditions"):
        lines.append("")
        lines.append("成立条件：" + "；".join(mech["conditions"]))
    ev_for = json.loads(d["evidence_for_json"]) if isinstance(d.get("evidence_for_json"), str) else d.get("evidence_for", [])
    ev_against = json.loads(d["evidence_against_json"]) if isinstance(d.get("evidence_against_json"), str) else d.get("evidence_against", [])
    cat = json.loads(d["catalysts_json"]) if isinstance(d.get("catalysts_json"), str) else d.get("catalysts", [])
    oq = json.loads(d["open_questions_json"]) if isinstance(d.get("open_questions_json"), str) else d.get("open_questions", [])
    lines.append("")
    lines.append("**支持证据**：")
    for e in ev_for[:6]:
        lines.append(f"- {e.get('claim', '')}：{e.get('evidence', '')}（{e.get('source', '')}, {e.get('as_of', '')}）")
    lines.append("")
    lines.append("**反对证据 / 替代解释**：")
    for e in ev_against[:6]:
        lines.append(f"- {e.get('claim', '')}：{e.get('evidence', '')}")
    lines.append("")
    if cat:
        lines.append("**潜在催化**：" + "；".join(f"{c.get('date')} {c.get('title')}" for c in cat))
        lines.append("")
    lines.append("**需要深入研究**：")
    for q in oq:
        lines.append(f"- {q}")
    lines.append("")
    lines.append(f"**失效条件**：{d.get('invalidation', '')}")
    gap = (disc.get("expectation_gap") or {})
    if gap:
        lines.append("**预期差度量（可测代理）**：")
        if gap.get("value") is None:
            lines.append("- 不可测量（无可用估值/仓位/残差背离代理）——该候选不得进入重点研究")
        else:
            for name, comp in (gap.get("components") or {}).items():
                if comp.get("value") is None:
                    lines.append(f"- `{name}`：不可用（{comp.get('reason','')}）")
                else:
                    lines.append(f"- `{name}`：{comp['value']:.2f}（权重 {comp['weight']}；"
                                 f"{comp.get('evidence',{}).get('meaning','')}）")
            lines.append(f"- 合计 {gap['value']:.2f}，代理覆盖度 {gap.get('confidence',0):.0%}")
        lines.append("")
    dq = json.loads(d["data_quality"]) if isinstance(d.get("data_quality"), str) else d.get("data_quality", {})
    if detail and dq:
        lines.append("")
        lines.append(f"**数据质量**：{dq.get('score', 'n/a')}；缺口：{'；'.join(dq.get('gaps', []))}")
    lines.append("")
    return "\n".join(lines)


def build_markdown(store: Store, fs: FeatureSet, anomalies: pd.DataFrame,
                   transmissions: pd.DataFrame, mechanisms: list[Any],
                   opportunities: list[dict[str, Any]], scan_meta: dict[str, Any],
                   quality_issues: pd.DataFrame | None = None) -> str:
    as_of = scan_meta.get("as_of", fs.as_of)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        f"# 全球投资机会发现报告 — {as_of}",
        "",
        f"- 生成时间：{now}",
        f"- 扫描 ID：`{scan_meta.get('scan_id', '')}`",
        f"- 特征版本：`{scan_meta.get('feature_version', '')}`；配置哈希：`{scan_meta.get('config_hash', '')[:16]}`",
        f"- 数据快照哈希：`{scan_meta.get('data_hash', '')[:16]}`",
        f"- 覆盖：{scan_meta.get('n_instruments', 0)} 个交易标的"
        + (f"（配置 {len(load_universe().instruments)} 个，其余历史长度不足或数据缺失）"
           if scan_meta.get('n_instruments', 0) != len(load_universe().instruments) else "")
        + f"、{scan_meta.get('n_macro_series', 0)} 个宏观序列、"
        f"{scan_meta.get('n_curve_systems', 0)} 条收益率曲线、{scan_meta.get('n_positioning_series', 0)} 个仓位序列",
        "",
        "> 本报告是研究线索，不是交易建议。机会评分衡量研究优先级，不衡量预期收益；",
        "> 每条异常都带证据字段（阈值、公式、原始值），可用 `goe scan --as-of <日期>` 重建特征层复算；",
        "> 异常记录持久化在 `anomalies` 表（含观测日/可用日）；机会与状态变更在 `opportunities` / `opportunity_events`。",
        (f"> 数据就绪：覆盖率 {scan_meta.get('data_readiness',{}).get('coverage',0):.0%}，"
         f"最后价格 {scan_meta.get('data_readiness',{}).get('last_price_date','')}，"
         f"降级={scan_meta.get('data_readiness',{}).get('degraded')}。" if scan_meta.get('data_readiness') else ""),
        ("> 数据告警：" + "；".join((scan_meta.get('data_readiness') or {}).get('warnings') or [])
         + (f"（过期序列 {len((scan_meta.get('data_readiness') or {}).get('stale_indicators') or [])} 条）"
            if (scan_meta.get('data_readiness') or {}).get('stale_indicators') else "")
         if (scan_meta.get('data_readiness') or {}).get('warnings') else ""),
        (f"> 采集状态：{scan_meta.get('ingest',{}).get('status')}；"
         f"错误源：{', '.join(k for k,v in (scan_meta.get('ingest') or {}).items() if k.endswith('_error')) or '无'}。"
         if (scan_meta.get('ingest') or {}).get('status') == 'partial' else ""),
        "",
        "## 1. 市场状态快照",
        "",
        "### 1.1 主要资产收益与风险",
        "",
    ]
    snap = market_snapshot(fs)
    if not snap.empty:
        lines.append("| 资产 | 1周 | 1月 | 3月 | 12月 | 3月年化波动 | 距1年高点 |")
        lines.append("|---|---|---|---|---|---|---|")
        for r in snap.to_dict("records"):
            vol = r.get("vol_3m")
            vol_txt = f"{vol * 100:.1f}%" if pd.notna(vol) else "n/a"
            lines.append(f"| {r['name']} (`{r['id']}`) | {_pct(r.get('1w'))} | {_pct(r.get('1m'))} | "
                         f"{_pct(r.get('3m'))} | {_pct(r.get('12m'))} | {vol_txt} | "
                         f"{_pct(r.get('dd_1y'))} |")
    lines += ["", "### 1.2 收益率曲线", ""]
    curves = curve_snapshot(fs)
    if not curves.empty:
        lines.append("| 曲线 | 2Y | 10Y | 30Y | 2s10s | 1月变化(pp) |")
        lines.append("|---|---|---|---|---|---|")
        for _, r in curves.iterrows():
            lines.append(f"| {r['curve']} | {_num(r.get('2Y'))} | {_num(r.get('10Y'))} | {_num(r.get('30Y'))} | "
                         f"{_num(r.get('2s10s'))} | {_num(r.get('2s10s_1m_chg'), 3)} |")
    stale = scan_meta.get("stale_macro_series") or {}
    if stale:
        lines.append(f"**数据陈旧剔除**：{len(stale)} 个宏观序列因最新观测过旧未参与本次判断（"
                     + "、".join(f"`{k}` {v} 天" for k, v in list(stale.items())[:6])
                     + ("…" if len(stale) > 6 else "") + "）。")
        lines.append("")
    lines += ["### 1.3 宏观序列（按发布滞后处理）", ""]
    macro = macro_snapshot(fs)
    if not macro.empty:
        lines.append("| 序列 | 最新值 | 近3期变化 | 3年z |")
        lines.append("|---|---|---|---|")
        for r in macro.to_dict("records"):
            lines.append(f"| {_name(r['id'])} (`{r['id']}`) | {_num(r.get('value'))} | "
                         f"{_num(r.get('change_3p'), 3)} | {_num(r.get('z_3y'))} |")
    else:
        lines.append("_宏观序列尚不可用（数据源未接入或尚未完成回填）。_")

    lines += ["", "## 2. 异常检测结果", "",
              f"回放窗口内共 {len(anomalies)} 条异常（去重/限流后）；最近 5 个日历日 "
              f"{len(anomalies[pd.to_datetime(anomalies['date']) >= pd.to_datetime(anomalies['date']).max() - pd.Timedelta(days=5)]) if not anomalies.empty else 0} 条。"
              + ("家族分布：" + "；".join(f"{k} {v}" for k, v in anomalies.family.value_counts().to_dict().items()) if not anomalies.empty else ""),
              ""]
    lines.append(render_anomaly_table(anomalies))

    lines += ["## 3. 宏观传导机制（被激活）", ""]
    if mechanisms:
        for m in mechanisms:
            lines.append(f"### {m.mechanism_id} — {m.title}")
            lines.append(f"- 状态：`{m.status}`；置信度：{m.confidence:.2f}；家族：{m.family}")
            lines.append(f"- 触发：'" + "；".join(f"{t['entity_id']}({t['direction']}, {t['detector']})" for t in m.triggers) + "'")
            lines.append(f"- 受影响资产：" + "；".join(f"{a['id']}({a['role']})" for a in m.assets))
            for e in m.evidence_for[:3]:
                lines.append(f"- 支持：{e.get('statement', '')}")
            for e in m.evidence_against[:3]:
                lines.append(f"- 反对/不足：{e.get('statement', '')}" + (f"（{e.get('reason')}）" if e.get('reason') else ""))
            if m.conditions:
                lines.append("- 成立条件：" + "；".join(m.conditions))
            if m.falsifiers:
                lines.append("- 反证条件：" + "；".join(m.falsifiers[:3]))
            lines.append("")
    else:
        lines.append("_本次没有机制满足激活条件。_\n")

    lines += ["## 4. 投资机会候选池", "",
              f"共 {len(opportunities)} 个候选："
              + "；".join(f"{s} {n}" for s, n in pd.Series([o["status"] for o in opportunities]).value_counts().items())
              if opportunities else "_本次扫描未生成候选机会。这本身是一个有效结果：没有组合同时满足异常、机制与证据门槛。_",
              ""]
    for rec in opportunities:
        if rec["status"] in ("deep_research", "watch", "new"):
            lines.append(render_opportunity(rec))
    others = [r for r in opportunities if r["status"] not in ("deep_research", "watch", "new")]
    if others:
        lines += ["### 其他记录（暂不研究/已排除）", "", "| 机会 | 评分 | 状态 | 原因 |", "|---|---|---|---|"]
        for r in others[:20]:
            lines.append(f"| {r['opportunity_id']} {r['title']} | {r['score']:.2f} | {r['status']} | {r.get('status_reason', '')} |")
        lines.append("")

    price_issues = scan_meta.get("price_data_issues") or []
    if price_issues:
        lines.append(f"**价格数据清洗**：本次处理 {len(price_issues)} 项（拆股调整/水平重定基/毛刺隔离/非正价格）。")
        for it in price_issues[:8]:
            lines.append(f"- `{it['instrument_id']}` {it['kind']} {it.get('date','')} {it.get('dates','')}")
        lines.append("")
    lines += ["## 5. 数据质量与已知限制", ""]
    if quality_issues is not None and not quality_issues.empty:
        lines.append("| 时间 | 对象 | 问题码 | 严重度 | 说明 |")
        lines.append("|---|---|---|---|---|")
        for r in quality_issues.head(15).itertuples(index=False):
            lines.append(f"| {r.created_at} | {r.target} | {r.code} | {r.severity} | {str(r.detail)[:120]} |")
    else:
        lines.append("_本次运行未记录新的数据质量问题。_")
    lines += [
        "",
        "已知限制（长期有效）：",
        "- 价格来自 Yahoo Finance（聚合层），不是交易所原始行情；期货为连续/前月合约，未做展期调整。",
        "- 信用利差使用 HYG/IEF 相对表现代理，不是 OAS；中国/欧洲部分宏观序列存在发布滞后。",
        "- CFTC 仓位为周度、滞后 4 天发布；仅覆盖期货。",
        "- 分析师盈利预期、ETF 资金流、期权隐含分布未接入，相关结论须在 investment-agent 中补充验证。",
        "",
        "## 6. 下一步研究队列",
        "",
    ]
    queue = [r for r in opportunities if r["status"] == "deep_research"]
    if queue:
        for r in queue[:10]:
            lines.append(f"- `{r['opportunity_id']}` {r['title']} → 已生成 investment-agent 研究任务（见 exports/research_tasks/）")
    else:
        lines.append("- 本次没有达到“重点研究”门槛的候选；持续观察项见上表。")
    lines += ["", "---", "", f"*由 Global Opportunity Engine {scan_meta.get('engine_version', '')} 生成。"
              f"复现：`goe scan --as-of {as_of} --no-ingest`*", ""]
    return "\n".join(lines)


def write_reports(out_dir: Path, store: Store, fs: FeatureSet, anomalies: pd.DataFrame,
                  transmissions: pd.DataFrame, mechanisms: list[Any], opportunities: list[dict[str, Any]],
                  scan_meta: dict[str, Any], quality_issues: pd.DataFrame | None = None) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    as_of = scan_meta["as_of"]
    md = build_markdown(store, fs, anomalies, transmissions, mechanisms, opportunities, scan_meta, quality_issues)
    md_path = out_dir / f"report_{as_of}.md"
    md_path.write_text(md, encoding="utf-8")
    json_path = out_dir / f"scan_{as_of}.json"
    json_path.write_text(json.dumps({
        "meta": scan_meta,
        "anomalies": anomalies.to_dict("records") if not anomalies.empty else [],
        "transmissions": transmissions.to_dict("records") if not transmissions.empty else [],
        "opportunities": opportunities,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return {"markdown": str(md_path), "json": str(json_path)}
