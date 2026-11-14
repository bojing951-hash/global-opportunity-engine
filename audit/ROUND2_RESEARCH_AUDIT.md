# ROUND 2 — 独立研究方法 / A→B 交接审计（Audit C + E）

- 审计对象：`HEAD 7c5df4c` + 未提交变更（`goe/db.py`、`goe/pipeline.py`、`goe/readiness.py`、两个测试文件）；`as_of 2026-11-13`。
- 数据快照：`scan-20261114T053317Z-b68a9f`（2026-11-14 05:33:17Z，1,649 条异常，18 个机会，9 watch / 7 low_priority / 2 excluded / **0 deep_research**）；冻结导出 `exports/pipeline_2026-11-13.json`、`reports/scan_2026-11-13.json`、`reports/report_2026-11-13.md`。审计时间 2026-11-14 13:20–13:45 HKT。
- 方法：只读 SQL/JSON + `.venv/bin/python` 独立复算（FeatureBuilder、expectations、forward_eval、评分公式）；只读 `goe handoff --dry-run` 与 B 的 `ia_cli.py research-run`（输出到 `/tmp`，未写仓库）；未改代码/配置/数据/测试/git，唯一写入本文件。
- **环境事实（重要）**：审计期间 `data/goe.db` 被并发清空/重扫至少两次（13:31 与 13:43 读到 0 行），13:33 由新扫描重建。当前 18 个机会、top-5 分数与 13:23 读到的旧扫描逐字一致，且与冻结导出一致；但生产库不是稳定审计对象。下面的机会 JSON 证据来自 13:23/13:34 的 DB 读取与 05:33 冻结导出；可复算字段不受影响。
- **并发修复（13:30–13:46，必须知道）**：另一进程在此期间修改了 13 个文件（`goe/opportunities.py` +59、`features.py`、`anomalies.py`、`integration/exporter.py`、`reports.py`、`tests/test_scoring.py` 等）。其中与本文直接相关的：
  - `catalyst` 负天数已修（`0 <= days <= 10`；过去政策不再 1.0）——§3 P1 #3 在**当前代码**已修，但 **05:33 扫描/本报告 top-5 是修复前产物**。
  - `apply_lifecycle` 已对“仍在当前集合”的指纹也评估 `invalidation_checks`——§3 P1 #1 的“失效不执行”一半在**当前代码**已修；`evidence_quality` 仍不含 `evidence_against`，`expected_direction` 仍未使用。
  - 新增最终 theme cap（同 theme 只留一个，修 SPY 两次）、`data_degraded` 降级、期货 roll risk；`build_research_question` 的新文本/`tests/test_exporter.py` 的“赔率”断言也是本次并发修改（11:36 的旧 run 用旧文本）。
  - **结论：本报告的表格/数字是 05:33 修复前快照；当前代码已部分修复。必须重跑 `goe scan` 才能看新排序，并重跑 `goe replay --cases`/handoff 才能确认修复。下面的“当前已修”只表示代码已改，不表示 05:33 产物已修。本文的 `goe/opportunities.py:...` 行号是 13:28 审计快照；13:46 并发修改已使行号偏移，定位请按函数名（`_score`/`apply_lifecycle`/`_policy_event_repricing`），不要按行号。**


## 1. 判决

**FAIL（仅 Audit C/E：研究方法与 A→B 交接）；工程/数据管线可运行，不判全仓库 FAIL。**

支持“工程可运行”的证据：未提交的 readiness/事务改动有 17 项定向测试通过（`pytest tests/test_pipeline_e2e.py tests/test_readiness_handoff.py -q` → 17 passed, 23.7s）；05:33 扫描 success；数据覆盖 125/125；1,649 条异常；`goe handoff` 现在对非 `ok_valid` 返回 exit 2（round-1 的 CLI exit 0 已修）。

不判 PASS 的最强反证（均为 NEW，详见 §3）：

1. **top-1 是过去事件的追溯叙事**：OPP-0001 QQQ 的 `catalyst=1.0` 来自 2026-10-16（BIS 月频“可用日”，比 as_of 早 28 天）；`days=-28 <= 10` 直接命中最高档。修正为 0.1 后 0.6702→**0.5802**，top-1 让位。
2. **top-2 自己的失效条件已满足**：OPP-0002 的 `invalidation_checks` 是 `VIX3M 1m return_z_3y ∈ [-1,1]`；2026-11-12 实际 **0.6619**，条件成立；但 `apply_lifecycle` 对“仍在当前集合”的候选直接 `continue`，从不评估。候选仍为 top-2。
3. **top-3 的中央机制符号相反**：OPP-0003 XLP 的 M05 机制 1 通过 / 4 失败、confidence **0.14**；核心检验 oil→CPI 相关 **-0.26**（期望 +1，近端符号一致率 3%）。机制对 XLP 的 `expected_direction=down`，而 XLP 1m **+5.8%**，残差 **+10.5% (z=3.83)** 被计为 gap **1.0**。`expected_direction` 在全仓库只被写入、从未被读取。**56.2%** 的分数来自同一价格变动（anomaly 0.22×0.9991 + gap 0.20×0.4 + repricing 0.12×0.5584）。
4. **预期差不是 as_of 的测量**：residual 的 `sample.iloc[::21]` 把“当前”锁在 **2026-10-30**，而价格/特征到 11-12；用最新行重算：QQQ gap 0.3176→**0.0131**（z -2.691→-1.549），XLP 0.4→**0.0931**，EEM 0.4→**0.1227**。换一个合法的 PIT 历史起点（全历史 vs 实盘 6.5 年）QQQ/EEM gap 直接变 **0.0**。top-5 对两个可辩护的测量口径都不稳定。
5. **7/7 历史验证不是“检测到现象”**：`found_detectors` 是窗口内**全市场**检测器集合，不是 case 实体；SVB 的 3 个期望检测器（credit_stress / drawdown / vol）在 case 实体上一次都没出现（`earliest_detection` 只有 price_return_shock、relative_strength），仍因全市场命中而 `detection_ok=true`。7/7 中 5/7 `mechanism_ok=false`；SVB 的 `relevant_candidates` 是 TLT VIX / XLF 政策 / HYG VIX，而不是信用/银行。
6. **A→B 仍不能交付**：当前问题（已删“估值与赔率”并写明“不构成投资建议”）在 B 的 `research` 仍返回 **`out_of_scope`**；A 的 `parse_research_artifact` 把“拒绝”归类为 **`partial`**（`run_ok=true` + 17 条证据 + 1 个 semantic_ok=false），任务状态 `not_completed:partial`，不是 `not_completed:out_of_scope`。17 条证据全是 `VP-VIEW-* [INSUFFICIENT_EVIDENCE]` 的 L2 观点，L1 `rows=[]`，L3/L4 `produced=false`；若 S8 没失败，parser 会因“17 条证据”判 `ok_valid`。这不是高质量研究交付。

判决：**研究方法层 FAIL，交接层 FAIL（B 限制为主因，A 有解析/契约缺陷）**；没有发现新的 P0（无伪造数据/前视），但有 6 个新 P1。审计快照是 05:33 产物；当前 13:46 并发代码已修 catalyst 与 invalidation 的一半（见 §0），本报告的 top-5/分数需重扫后复验。

## 2. 复现（关键数字）

```bash
# 快照 / 计数（审计时 DB 被并发清空，以下用冻结导出复核）
sqlite3 data/goe.db "select scan_id,status,as_of from scan_runs; select count(*) from opportunities;"
python - <<'PY'
import json; d=json.load(open('exports/pipeline_2026-11-13.json'))
for o in d['opportunities'][:5]:
    q=o['opportunity']; print(q['opportunity_id'], q['score'], q['status'], q['score_breakdown'])
PY

# 定向测试（未提交改动）
.venv/bin/python -m pytest tests/test_pipeline_e2e.py tests/test_readiness_handoff.py -q -o addopts=""   # 17 passed

# 预期差：实盘 6.5 年窗口 + 最新行对照（约 1–2 分钟）
.venv/bin/python - <<'PY'
from goe.db import Store
from goe.features import FeatureBuilder
from goe.expectations import compute_expectation_gap
fs=FeatureBuilder(Store('data/goe.db'), as_of='2026-11-13', history_start='2020-05-13').build()
for iid in ['US_EQ_QQQ','US_EQ_SPY','US_SEC_XLP','WORLD_EQ_EEM']:
    g=compute_expectation_gap(fs,iid); print(iid,g.value,g.confidence,
      {k:(v.value,v.evidence.get('as_of_return_date'),v.evidence.get('residual_z')) for k,v in g.components.items()})
PY

# 当前问题 → B（只读，输出到 /tmp）
.venv/bin/python -m goe.cli handoff --ia-path /Users/cast/investment-agent-dev --limit 1 --dry-run
# /tmp/goe_audit_run/.../report.json: run_ok=true, 17 evidence, S8 out_of_scope, L3/L4 produced=false
```

关键观测：

| 项目 | 值 |
|---|---|
| OPP-0001 评分 | `0.22×1.0 + 0.18×0.65 + 0.20×0.3176 + 0.12×0.0708 + 0.10×1.0 + 0.06×1.0 + 0.06×1.0 + 0.06×0.6867 = 0.6702` |
| 同上，catalyst 1.0→0.1 | **0.5802**（QQQ 从 #1 掉到 #5） |
| 同上，gap 用 11-12 最新行 | gap 0.3176→0.0131，score **0.6092**；两者同时修 **0.5192** |
| OPP-0002 gap | 0.1392 = (0.35×0.3977 + 0.40×0)/0.75 × 0.75；residual 0 来自 SPY 自身市场驱动 R²=1.0 |
| OPP-0003 gap | 0.4 = 1.0×0.4（残差 +10.52%、z=3.833，2026-10-30） |
| OPP-0005 gap | 0.4（z=-3.177，2026-10-30）；最新 11-12 z=-1.96 → 0.1227 |
| XLP 同源分数占比 | 0.3668 / 0.6532 = **56.2%**（anomaly+gap+repricing） |
| QQQ / EEM 同源占比 | 43.6% / 51.3% |
| VIX 期限 | 11-05 VIX/VIX3M=**1.1029**（倒挂）；11-09 VIX3M -15.24% 是波动回落；11-12 比值 **0.9322**（contango） |
| VIX3M 1m return_z_3y（11-12） | **0.6619** ∈ [-1,1] → OPP-0002 自动失效条件已触发 |
| 11-05 单日 | SPY 766.81→733.00（**-4.41%**）；QQQ 691.95→647.05（**-6.49%**）；11-09 SPY +2.37%、QQQ +3.53% |
| M05 | 1 pass / 4 fail；confidence 0.14；oil→CPI -0.26（期望 +1，符号一致率 3%） |
| M12 | 2 pass / 2 fail；confidence 0.55；VIX>25 后 SPY 21d 均值 +2.5%、命中率 28%（conditional_weak） |
| 证据质量 | top-5 全部 0.6867；代码 `0.6×tier + 0.4×独立性`，M05 的 0.14 机制置信度不进入 |
| 18 个候选 | 8 divergence + 6 regime + 4 event（caps 8/6/4 全部饱和）；M12 3 个、M05 3 个 |

## 3. NEW 问题表

| 严重度 | 位置 | 证据 | 影响 |
|---|---|---|---|
| **P1** | `goe/opportunities.py:1370`；`goe/expectations.py:197`；`goe/transmission/evaluator.py:490` | 负证据只记录不排序：OPP-0002 的 `VIX3M z=0.6619` 已满足自身 `invalidation_checks`，仍 top-2；OPP-0003 的中央检验 -0.26、机制 0.14、`expected_direction=down`，仍 top-3。`apply_lifecycle` 对当前指纹 `continue`；`evidence_quality` 不含 `evidence_against`/机制置信度；`expected_direction` 全仓库只写不读 | 系统的“可证伪/自动失效”是装饰；top-2/top-3 的负证据不改变排名，研究价值分数无法区分支持与反驳。（**当前 13:46 代码已修 invalidation 一半；evidence_against/expected_direction 未修**） |
| **P1** | `goe/opportunities.py:1206,1210-1217`；`docs/SCORING.md:83-85`；`FINAL_ACCEPTANCE §3` | 同一价格变动三重计数：XLP 的 relative_strength_extreme + drawdown_near_high + price_up 是同一 +5.8%，又进入 gap（残差 +10.5%）与 repricing（MA gap 8.38%）；XLP 56.2%、QQQ 43.6%、EEM 51.3% 的分数来自同一 move。代码注释称“drawdown 已计入异常，不重复”，但 MA gap 与残差仍是同一价格 | “八个独立维度”不成立；一个价格冲击可把候选推入 top-3；“score double counting removed”声明与数据不符 |
| **P1** | `goe/opportunities.py:1049,1210-1212` | 过去政策事件被当作 ≤10 天催化：OPP-0001/0004/0007 的 catalyst 日期 2026-10-16，as_of 2026-11-13，`days=-28`，`cat=1.0`；文档/报告写“政策事件在 10 天内”。修正后 QQQ 0.6702→0.5802、SPY 0.6448→0.5548、N225 0.5807→0.4907 | 直接改变交付给 B 的 #1；3 个过去政策候选被系统性抬高 0.09；这是“追溯性叙事”而非事前催化。（**当前 13:46 代码已修；05:33 产物未修**） |
| **P1** | `goe/expectations.py:197-199`；`goe/pipeline.py:75` | 残差“当前”被 `sample.iloc[::21]` 锁在 2026-10-30（非 as_of 11-12）：QQQ 10-30 z=-2.691、gap 0.3176；11-12 z=-1.549、gap 0.0131；XLP 0.4→0.0931；EEM 0.4→0.1227。历史起点从实盘 6.5 年换为全历史（同一 as_of、同一 PIT）：QQQ gap 0.3176→**0.0**、EEM 0.4→**0.0**、XLP 0.4→0.2328。`_hist_start=as_of-6y6m` 是硬编码，未写入 scan meta/discovery | gap 占 score 20%，top-1/top-3/top-5 的“预期差”不是 as_of 的测量；同一数据的合法重建可让 QQQ/EEM 的 gap 归零；不可从 artifact 复现（n_obs=73 但无 window 记录） |
| **P1** | `goe/integration/ia_adapter.py:66-87`；`exports/ia_runs/OPP-0001/20261114T033647Z.../report.json`；`/tmp/goe_audit_run/.../report.json` | 当前问题（无“估值与赔率”、有“不构成投资建议”）在 B 仍 `out_of_scope`；`parse_research_artifact` 只看 run_ok/证据数/semantic_ok=false → `partial`，不读 step envelope 的 `data.status=out_of_scope`；任务 `not_completed:partial`，不是 refused。17 条证据全是 L2 `VP-VIEW INSUFFICIENT_EVIDENCE`，L1 `rows=[]`，L3/L4 `produced=false`；S8 若返回语义成功，parser 会以 17 条泛化证据判 `ok_valid` | A 不能区分“B 拒绝/越界”“数据不足”“部分失败”；即使 B “成功”，交付的也是事实/观点包，不是问题要求的可证伪研究；A 的“语义成功”判据可被泛化证据绕过 |
| **P1** | `goe/validation.py:86,195-204` | `found_detectors` 是窗口内全市场集合；SVB 期望的 `credit_stress/drawdown_extreme/vol_regime_shift` 在 4 个 case 实体上 0 命中（earliest 只有 price/relative），仍 pass；China/Gold 也依赖全局 `breadth_extreme`/`cross_asset_divergence`。7/7 中 5/7 `mechanism_ok=false`；SVB 相关候选 TLT VIX/XLF 政策/HYG VIX；UK 是 EWU 政策、Japan 是 N225 政策；`mechanism_ok=any(mixed)` 允许 0.14/0.22 | “7/7 检测”几乎不可失败（全市场 930–2,602 条异常，期望检测器总会命中）；案例通过的是“同实体上任何 archetype”，不是案例现象/机制；不能作为筛选能力证据 |
| **P2** | `goe/evaluation.py:89,120-170,200-250`；`audit/research_quality_*.json`；`audit/RESEARCH_QUALITY.md` | C 卡 8/12 带 mechanisms，A 1/12、B 2/12；C 均值 1.2917 vs B 1.2708（+0.0209，等于一个对象一个标准 1 分）；rater 的 `beyond_price/falsifiable` 与“有机制”同向，X09/X18 对 0.14/0.22 机制仍给 2/2。ID 按方法分块（X01-03 A、X04-06 B、X07-09 C…），输入打乱但 ID 泄露；3 对重复实体（USDJPY、CHINEXT、PL），有效 n=33 非 36；`dup` 只数同方法主题重复 | “盲评”对 C 的事实卡更富机制信息，评审在 C 自己提供的结构上打分；+0.02 不是独立选择优势；重复实体被计为独立观测；`Precision@3` 实为 12 个对象的 ≥1.5 比例 |
| **P2** | `goe/forward_eval.py:60-95`；`audit/FORWARD_RETURNS.md` | 方法资产类严重不平衡：C 10/12 股票（含 SPY 两次）+1 FX+1 商品；A 9/12 非股票（6 商品+2 波动+1 加密）+3 股票；B 6/12 非股票（3 FX+3 固收）+6 股票。C 的 USDJPY 是汇率对；N225/EWU/VGK 用本币收益；C 含 SPY 自身（excess=0 构造）。引擎 3m +4.07%、excess -2.50%、beat 25%；B +4.75%/-1.81%/33% | “excess vs SPY”不是同资产类比较；C 的股票集中使其相对 SPY 的比较机械；负结果被诚实披露（保留 2025-06-30 C 0.67 vs B 1.50），但“明确否定”对 n=12/混合资产过强 |
| **P2** | `goe/opportunities.py:1217-1218`；`config/scoring.yaml:60`；`docs/SCORING.md:23` | 文档/配置：`0.5×tier + 0.3×独立 + 0.2×机制置信度`；代码：`0.6×tier + 0.4×独立`，无机制项。top-5 全部 0.6867；M05 0.14、M12 0.55 的 evidence_quality 完全相同；4 个失败检验不影响分数 | “证据质量”不区分支持/反驳/机制强弱；与文档不一致；低置信机制不受惩罚 |
| **P2** | `goe/opportunities.py:1178-1186,307`；`config/scoring.yaml:54` | `economic_impact` 的 breadth = 机制映射资产数/5；M05/M12 各 5 个 → 1.0，event_revision 的 `mechanism_assets=1` → 0.2；0.14 的 M05 也拿满 breadth；per-mechanism cap=3，M12/M05 各 3 个，top-10 中 6 个来自这两条机制 | 机制配置的资产数量（而非证据强度）系统性抬高 regime 候选；cap 3 不足以防止“一条弱机制刷 3 个候选”；18 个候选中 6 个来自两条机制 |
| **P2** | `goe/opportunities.py:1270-1288`；`config/scoring.yaml:62-71`；`goe/integration/ia_adapter.py:218` | 0/18 达到 deep_research 0.68；`min_expectation_gap=0.15`、`min_expectation_confidence=0.5`、`min_deep_research_data_quality=0.5`、机制 conf≥0.40+2 FDR 全部在 `if d.status=="deep_research"` 内，生产从未执行；`require_mechanism_or_divergence` 配置从未被读取；caps 8/6/4 全饱和 = 18；`research_queue` 16（含 7 low）而 `run_queue` 只跑 9 | 门禁是死代码；“18 个候选”不是 18 个高价值对象，而是 caps 填满；`handoff` 把 watch 当研究任务送 B（文档承认），与 deep_research 语义冲突 |
| **P2** | `goe/expectations.py:104-135`；`config/macro.yaml:99`；`goe/readiness.py:178-184`；`reports/report_2026-11-13.md` | `US_CAPE` 最后 2023-09-01（1169 天）；QQQ/SPY 的 valuation 永远 null；gap 覆盖度 40%/75%，0.25 权重从未可用。readiness `stale_indicators` 有 US_CAPE，但 `warnings` 只列 EA_HICP（`if key_stale` 分支丢弃非关键 stale）；scan `ok=true, degraded=true` | “估值/持仓/残差”三维实际只有两维（且估值长期死亡）；US equity 的 gap 上限被系统性压低；readiness 未把死估值序列作为关键警告 |
| **P2** | `goe/expectations.py:143-159`；`config/universe.yaml` | 非美资产的“market”驱动大多是 SPY 回退：`resolve_benchmark(CN_EQ_CSI300/HK_EQ_HSI/JP_EQ_N225/EA_EQ_SX5E)=None` → 取 `US_EQ_SPY`；`WORLD_EQ_EEM` 用 `WORLD_EQ_EFA`；只有 CN/HK 额外加 CNY，日/欧没有 JPY/EUR。R² 门槛 0.10 仍能过 | 中国 A 股/港股/日股/欧股的 residual 是“相对 SPY/EAFE 的跨国相对收益”，不是本地预期差；例如 CSI300 用 SPY 作 market，残差可只是中外风险轮动；这正是 prompt 问的“China equity with SPY as market”不可解释问题 |
| **P2** | `goe/expectations.py:143-159`；OPP-0002/0004 | SPY 的 market driver 是 SPY 自身，R²=1.0、residual=0.0；该零残差仍作为 available component，confidence 0.75（若排除则 0.35）；positioning 30.1 分位 → `|0.301-0.5|×2=0.3977`，不是“单边极端”；gap 0.1392 < `min_gap 0.15`，但门槛是死代码 | top-2/top-4 的 0.1392 gap 来自“30 分位 + 恒零残差”；confidence 被虚增；`min_gap` 本应拒绝该强度 |
| **P2** | `goe/opportunities.py:980-1055` | 政策“事件日”是 BIS 月频序列的 `available_date` 2026-10-16，不是 FOMC 决议日（月频值 2026-09-01，实际决议日不可知）；1m 收益/gap/“20 个交易日”都锚在这个可用日；事件在 as_of 前 28 天（真实决议更早） | 追溯性更强；“事件后 20 日重定价”失效条件与收益窗口错位；catalyst/event_revision 的日期语义不成立 |
| **P2** | `config/scoring.yaml:55-60`；`docs/SCORING.md:18-20,35`；`goe/opportunities.py:1206` | `repricing_potential` 三套定义：config “|z| vs 200d MA + 5y valuation + vol scaling”；docs `0.6×MA + 0.4×drawdown`；代码只有 `|ma_gap|/0.15`。`expectation_gap` 的 docs 写“近 3 个月收益”，代码是 1 个月；**config 仍写 `0.6 × mechanism confidence for regime_repricing`（代码已不用）**；`economic_impact` docs breadth/3，代码 /5；`residual ≥38 obs` vs 代码 36+5 | 文档/配置/代码不一致；审计者按 docs/config 复算会得到不同分数；`repricing` 对“近高位”资产是动量而非“均值回归空间” |
| **P3** | `goe/opportunities.py:540-670`；OPP-0012/0013/0016/0017 | 4 个 divergence 候选 `anomaly_strength=0.0`、`discovery.anomalies=[]`，但标题/`what` 写“价格异常下跌”，score 0.37–0.50；config 声称“异常是必要条件” | “异常”叙事没有异常记录；低价候选填充 18 个名额；与“少量高价值”冲突 |
| **P3** | `goe/db.py`/并发进程；`data/goe.db` | 13:31 与 13:43 两次读到 0 行；13:33 新扫描重建；`reports`/`exports` 被覆盖 | 生产库不是稳定审计对象；审计/验收必须 pin `scan_id` + artifact hash；本次只能以 05:33 导出/报告 + 13:23 读取为准 |

## 4. top-5 逐个：故事是否成立

**OPP-0001 QQQ（0.6702，watch，event_revision）**
故事：2026-09 BIS 月频政策利率 +0.25（可用日 10-16）→ QQQ 近 1 月 -5.6% → 未充分定价 → 重定价空间。系统未排除的竞争解释：11-05 单日 QQQ -6.49% vs SPY -4.41%（纳斯达克/科技特定冲击或全球风险冲击），11-09 又 +3.53% vs SPY +2.37%；1m 相对强弱 z=-5.1 的异常日期正是 11-05，单日贡献是 1m 相对弱势的显著组成；政策事件是 28 天前的月频数据发布，不是决策日；gap 用 10-30 的 -6.95%，miss 掉 11-05。结论：**“价格下跌”被当成“未定价的预期差”，但没有排除单日科技冲击/全球风险冲击**；`invalidation_checks=[]`，不可自动证伪。不是 P0 前视（数据都在 as_of 前），是研究叙事不成立。

**OPP-0002 SPY（0.6624，watch，regime_repricing M12）**
故事：VIX 期限结构倒挂 → 风险资产承压。实际：11-05 VIX/VIX3M=1.1029（真倒挂），11-09 VIX -22.3%、VIX3M -15.2%（波动回落），11-12 比值 0.9322（contango）。系统把 **11-09 VIX3M 下跌**当作触发异常；配置说“远月下跌相对近月更快才构成倒挂”，但 11-09 VIX 跌得比 VIX3M 更快，方向相反。自身失效条件（VIX3M 1m z∈[-1,1]）在 11-12 为 0.6619，已满足；仍在 top-2。支持证据是 VIX 水平与 SPY 的机械负相关（-0.84），不是期限结构；反对证据“VIX>25 后 SPY +2.5%、命中 28%”直接反驳继续承压。结论：**把波动正常化当成压力机制，因果方向/相位错误**。

**OPP-0003 XLP（0.6532，watch，regime_repricing M05）**
故事：能源→通胀→利润率→必需消费承压。实际：M05 0.14、1/5 通过；oil→CPI -0.26（期望 +1，3% 一致）；XLP 1m **+5.8%**、残差 **+10.5%**、处于 52 周高位；机制对 XLP 的预期是 **down**。系统把“XLP 跑赢/上涨”当成最大预期差（gap 1.0）和“重定价窗口”，但这是机制的反向证据。竞争解释：11-05 风险冲击下的防御性轮动（XLP 是低 beta 必需消费），以及 10 月利率/油价路径，不是能源通胀链。结论：**中央机制被自身证据反驳，价格方向与机制预期相反，仍为 top-3**；56.2% 分数来自同一价格变动。

**OPP-0004 SPY（0.6448，watch，event_revision）**
与 OPP-0001 同一政策事件、同一 11-05 异常（AN-97d16… 0.9205）、同一 gap 0.1392；SPY 在 OPP-0002 已经是 top-2。同一资产在同一扫描中出现两次（不同 archetype，theme 去重键含 archetype 故不去重）；1 条异常 + 2 条证据（BIS + engine），`min_evidence_items=2` 刚好通过；catalyst 1.0 过去事件。结论：**重复计数 + 追溯叙事**；不是独立研究对象。

**OPP-0005 EEM（0.6105，watch，regime_repricing M12）**
故事：VIX 期限结构 → EM 承压。实际：11-05 全球风险冲击，EEM 1m -5.0%、残差 -9.18%（相对 EFA/美元/利率），但 EM 高 beta 在 global risk-off 中跑输是正常 beta，不是“错误定价”；M12 的触发是 11-09 正常化；gap 0.4 来自 10-30 z=-3.177，最新 11-12 z=-1.96 → 0.1227；与 OPP-0015（divergence，同 EEM，gap 0.4）重复。结论：**高 beta 被当作预期差，且 gap 依赖采样相位**。

## 5. 预期差逐项

- **positioning**：`2×|pct−0.5|`。SPY 30.1 分位 → 0.3977，称“单边程度”；30 分位是温和低配，不是极端拥挤。没有方向/阈值；`0.1392` gap 主要来自这个 0.3977。CFTC 报告 11-07，as_of 11-13（6 天），新鲜度 OK；但 5 年分位/净头寸口径没有方向性。
- **valuation**：`US_CAPE` 最后 2023-09-01（1169 天），所有美国宽基/成长 valuation 为 null；0.25 权重不可用。readiness 只在 `stale_indicators` 列出，`warnings` 只报 EA_HICP；`ok=true`。报告有一行“US_CAPE 1169 天”，但候选层没有把“无估值”作为 gap 限制（只是 confidence 0.4/0.75）。
- **residual**：`_period_return` 是 **1 个月**（docs 写 3 个月）；`sample.iloc[::21]` 的“当前”是 10-30，不是 11-12；`fit` 用同一个 in-sample 残差 std 算 z；R² 门槛 0.10 极低（EEM 0.70、XLP 0.355、QQQ 0.865 全过），没有遗漏变量/结构断点/异方差检验；**非美资产的 market 驱动大多是 SPY 回退**（CN/HK/JP/EA 的 benchmark 为 None；EEM 用 EFA），只有 CN/HK 加 CNY；EEM 的残差是 EM vs DM 的正常风险轮动，XLP 的残差是防御轮动，SPY 的 market driver 是 SPY 自身（R²=1、residual 0，仍算 available，confidence 0.75）。
- **合成/置信度**：`value = weighted_mean × (avail_w/total_w)`；QQQ 0.3176=0.7941×0.4；SPY 0.1392=0.1856×0.75；XLP/EEM 0.4=1.0×0.4。覆盖度缩放是保守的，但也让 40% 覆盖的单一残差与 75% 覆盖的仓位+残差不可直接比较；`confidence` 只展示，不进入排序（除了死掉的 deep gate）。**数学本身对得上 DB 输入，问题在时间戳/窗口/覆盖度语义，不在算术。**

## 6. 评分/排序/门禁

- 复算 OPP-0001：0.670218 → 0.6702，公式/权重与 `config/scoring.yaml` 一致；caps 8/6/4 全部饱和，得到 18；per-mechanism 3 绑定（M05/M12 各 3）；theme 去重按 (archetype, theme, mechanism) 键，SPY 在 event/regime 两个 archetype 各出现一次，故不去重。
- 0/18 deep_research（最高 0.6702 < 0.68）。`min_expectation_gap`/`min_expectation_confidence`/`min_deep_research_data_quality`/机制 0.40+2 FDR 都只在 deep 分支；生产 0 个 deep，故从未执行。`require_mechanism_or_divergence` 在代码中无引用。
- 三种修正下的排序：
  - 现状：QQQ 0.6702 > SPY-M12 0.6624 > XLP 0.6532。
  - 只修 catalyst（过去政策→0.1）：SPY-M12 0.6624 > XLP 0.6532 > EEM 0.6105；QQQ **0.5802** 第 5。
  - 只修 gap（11-12 最新行）：SPY-M12 0.6624 > SPY-policy 0.6448 > QQQ 0.6092；QQQ 第 3，SPY 两个候选占据前二。
  - 两者都修：SPY-M12 0.6624 > OPP-0006 DXY 0.5956 > XLP 0.5918 > …；top-3 又是另一组。
  结论：**top-3 不是稳健排序，而是两个测量口径的产物**；分数差 0.008–0.017，任何一处修正都翻转。
- “18 个候选是否太多”：18 = 8 divergence + 6 regime + 4 event，caps 填满；其中 9 watch/7 low/2 excluded；`research_queue` 16（含 7 low）而 `run_queue` 只跑 9、`handoff --limit 1` 只跑 1。对“少量高价值研究对象”，存储层 18 过多（含 4 个 anomaly_strength=0 的 divergence、2 个 excluded）；交付层 1–3 个，但 top-1 是上述追溯候选。建议把 caps 与 deep gate 改为“先过 gap/机制/负证据门槛再计数”，而不是先填满 caps。

## 7. 历史案例

- 7/7 passed；检测逻辑 `found_detectors` 为全市场（`validation.py:86`），`detection_ok = any expected detector anywhere`（`:197`），`passed = detection_ok & relevant_candidate`（`:204`）。窗口 315–2,602 条异常、17 个检测器，任何 2–3 个常见检测器（price_return_shock、vol_regime_shift、drawdown_extreme）几乎必中。
- **SVB 是决定性反例**：case 实体 `US_CR_HYG/US_FI_IEF/US_SEC_XLF/US_VOL_VIX` 的 `earliest_detection` 只有 `price_return_shock`、`relative_strength_extreme`；期望的 `credit_stress/drawdown_extreme/vol_regime_shift` **0 命中**；仍把 `detectors_hit` 记为三项全中（全局）。`relevant_candidates` = TLT VIX、XLF 政策、HYG VIX；`mechanism_ok=true` 来自 M10 mixed 0.14。SVB 的 top candidate 是 CBOT Wheat（完全无关）。
- **UK / Japan / China / Gold**：相关候选分别是 UK EWU 政策、N225 政策、CSI300 政策、Gold 上行背离；机制 M01/M14/M04/M02 全部 unsupported。`FINAL_ACCEPTANCE`/`VALIDATION_RESULTS` 也承认 China 通过“observed-policy-action”、Gold 通过“symmetric upside-divergence”，不是机制检测。**7/7 是“同实体上任何候选”的弱口径，不是“检测到案例现象”。**
- 时间：每个 case 的 `hist = start-3y`，与实盘 `as_of-6y6m` 不同；expectation gap 是历史窗口依赖的（§3 P1），所以 case 的候选分数/排序不能代表 live；`detect_anomalies(since=start)` 的边界（round-1 N-02）在新扫描已降到 6/93 trend_break，但 case 首 10 天仍可能有伪检测；我没有逐案重跑。

## 8. A→B 交接

- **问题构建**：当前 `build_research_question` 已不含“估值与赔率”，并写“不构成投资建议；不要给买卖建议、收益承诺或目标价”“不要求给出概率或目标价”。所以“问赔率/建议”这个具体缺陷已修；但**修错了因果**：B 的拒绝不是“估值与赔率”措辞，而是其零模型 intent gate 只支持 4 类问题（美日政策利率差、美日 10Y 差、USDJPY、美国政策利率水平），并把当前“政策变化后的重定价：QQQ”判为投资建议/越界。我用当前问题直接跑 B 的 `research`：`out_of_scope`；跑完整 `research-run`：`run_ok=true`、17 evidence、S8 `out_of_scope`、L3/L4 `produced=false`、L1 `rows=[]`。A 的 ID/措辞没有映射到 B 的 registry，B 的 `S1_decompose` 也是 `metrics=[]`（问题未命中 B 的任何指标），S4/S5 被跳过。**即使 B 不拒绝也无法接地。**
- **拒绝 vs 部分**：`parse_research_artifact` 只看 `run_ok`、`n_evidence`、`semantic_ok=false`；B 的 `run_ok=true` + 1 个 S8 语义失败 → `partial`。B 的 step envelope 明确写 `data.status=out_of_scope`，A 不解析；任务 `not_completed:partial`，不是 `not_completed:out_of_scope`。因此 **A 没有正确区分 B 的拒绝/部分**（它区分了“成功/非成功”，但把拒绝并入部分）。CLI `cmd_handoff` 现在对非 ok_valid 返回 2，这是对的；但语义原因错。
- **A 缺陷还是 B 限制？** 主因是 **B 限制**：B 是 4 类事实问答的窄工具，且 `research-run` 明确 L3/L4 由编排 Agent 补作；A 不得修改 B。A 的次级缺陷：(a) 仍把 B 当通用 deep-research 端点，没有 pre-flight 能力检查/问题改写；(b) parser 不读 `out_of_scope`/`insufficient_data`/L3/L4/L1 rows；(c) `ok_valid` 只要求 ≥1 条证据，17 条泛化 L2 观点即可通过；(d) 当前问题未使用 B 的触发词/指标名，S1 零映射。**A 的“handoff”当前是不可用路径；`FINAL_ACCEPTANCE` 的 “partial, not success” 是诚实的，但不能称为“交付了研究任务”。**
- **如果 B 成功了，会是高质量研究任务吗？** 不会自动是。B 的 `research-run` 的 L3（AI 推断）/L4（条件情景）`produced=false`，A 没有调用 `research-attach` 补 L3/L4；17 条证据是 `INSUFFICIENT_EVIDENCE` 的 L2 views；L1 `rows=[]`。A 的问题本身还嵌入了未排除的竞争解释（11-05 单日冲击）、10-30 的 gap 日期、过去政策 catalyst。即使 S8 语义通过，交付的是“事实+观点包”，不是 A 问题要求的“可证伪情景/条件分析”。**这是 A 的契约/编排缺陷，不只是 B 的拒绝。**

## 9. 研究质量评测（RESEARCH_QUALITY / FORWARD_RETURNS）

- **盲评**：A 1.1667、B 1.2708、C 1.2917（+0.0209 = 单一对象单一标准 1 分）；Precision 0/0.25/0.5。C 卡 8/12 有 mechanisms，A 1/12、B 2/12；rater 的 `beyond_price/falsifiable` 正好由“有无机制”驱动，X09/X18 对 0.14/0.22 机制给 2/2。**引擎在“自己提供的机制结构”上得分，评测不是独立于 treatment 的**；文档称卡不含“引擎假设”，但 `mechanisms`（id/status/confidence/role）就是引擎假设。
- **匿名/重复**：ID 按方法分块（X01-03 A、X04-06 B、X07-09 C…），输入虽 `random.Random(42)` 打乱，但 ID 块泄露方法；3 对同 (as_of, entity) 重复（USDJPY X15/X18、CHINEXT X20/X23、PL X28/X33），有效 n=33；`dup` 只数同方法主题重复，故“重复主题 0”不覆盖跨方法重复；`Precision@3` 实为 12 个对象的 ≥1.5 比例。
- **前瞻**：C 10/12 股票（含 SPY 两次）+1 FX+1 商品，A 9/12 非股票（6 商品+2 波动+1 加密），B 6/12 非股票（3 FX+3 固收）；C 的 USDJPY 是汇率对，N225/EWU/VGK 是本币；C 的 SPY 自比 excess=0；n=12/方法。C +4.07%/−2.50%/25%，B +4.75%/−1.81%/33%，A +0.04%/−6.52%/25%。**负结果被诚实披露**（保留 2025-06-30 C 0.67 vs B 1.50；明确说没有跑赢简单异常排序），这一点应肯定；但“excess vs SPY”跨资产类不可比，C 的股票集中/含 SPY 使“beat SPY 25%”机械偏低，n=12 不足以“明确否定”。报告应同时披露资产类构成、重复实体、FX/本币口径；否则负结果的可解释性不足。
- **结论**：盲评的 +0.02 与前瞻的 −0.025 都在噪声内；现有证据只能支持“C 的卡片更有结构”，不能支持“C 选出的研究对象更值得研究”或“C 有超额收益”。这与文档的“引擎在盲评中更好”措辞相比应更保守。

## 10. 无法独立验证 / 限制

1. 没有重跑 `goe replay --cases` 全 7 案，只读了 `reports/validation_cases_20261114T033334Z.json` 与 `validation.py`；没有逐案重算分数。
2. 盲评只有 `audit/research_quality_ratings.json`（rater `independent-llm-1`），没有模型/版本/prompt/原始对话；“预注册”只有文档时间（11:39）晚于输入（11:12），无法证明先于输入；无法验证 rater 是否只看事实卡。
3. 没有跑非 dry-run 的 `goe handoff`（会写 DB/exports）；用 B 的 `research-run` 直接输出到 `/tmp` 代替，得到当前问题的 `out_of_scope`。真实 `research-attach`/L3/L4 编排未验证。
4. 无法验证 BIS/FOMC 的实际决议日、CFTC/BLS 的实际发布时刻/vintage；只能用 DB 的月频日期 + 配置滞后。政策“事件日”是可用日，真实决议日未知。
5. 生产 DB 在审计期间被并发清空/重扫（13:31、13:43 读到 0 行；13:33 重建）；我只能以 05:33 导出/报告 + 13:23 读取为准。**这是审计环境的可复现性问题，不是我能修的代码问题；建议后续 pin scan_id + artifact hash，审计期间不要 rollback/scan 生产库。**
6. 没有重跑完整 121/130 测试；只跑了未提交改动的 17 项定向测试（通过）。round-1 的 121 passed 未在本轮独立复验。
7. 未来收益/人类专家研究质量、机制因果识别、CFTC/BLS vintage、期货展期等仍不可验证。

## 11. 单一最重要新缺陷

**P1 — 审计快照（05:33）中，负证据不参与排序/生命周期；当前 13:46 代码只修了一半。**

- OPP-0002 的 `invalidation_checks`（VIX3M 1m z∈[-1,1]）在 2026-11-12 实际 **0.6619**，条件满足；审计快照的 `apply_lifecycle` 对仍在当前集合的指纹直接 `continue`，所以不失效，仍 top-2。**当前 13:46 代码已改为对 current 也评估 invalidation**（见 §0），但 05:33 扫描/导出仍是失效前产物；重扫后 OPP-0002 应被标 invalidated，需复验。
- OPP-0003 的 M05 中央检验 oil→CPI **-0.26**（期望 +1，3% 一致）、机制 confidence **0.14**、`expected_direction=down` 而 XLP +5.8%；`evidence_quality` 不含 `evidence_against`/机制置信度（`:1217-1218`），`expected_direction` 只写不读（`evaluator.py:490`），所以仍 top-3；56.2% 分数来自同一 move。**这一半当前代码未修。**
- 这不是单个 bug，而是“可证伪/自动失效/证据质量”三条声明的共同失效：系统记录了否定证据，却不让它改变排名或状态。审计快照的单一最重要新缺陷就是它；**当前代码修了 invalidation/催化/theme cap 之后，单一最重要的剩余新缺陷是 §3 P1 #4 的 gap 相位/窗口**（`goe/expectations.py:197` 未改）：gap 占 score 20%，05:33 的“当前”是 2026-10-30，换成 11-12 后 QQQ 0.3176→0.0131、XLP 0.4→0.0931、EEM 0.4→0.1227，换历史起点 QQQ/EEM→0.0；top-1/top-3/top-5 的核心证据不是 as_of 的测量。**其次是 evidence_against/expected_direction 进入 score。**

**建议的最小修复顺序（只恢复可证伪性/可复现性，不改研究结论）**：
1. `goe/expectations.py` 的 residual current 用 as_of 最新行，记录 `history_start`/窗口；residual 与 mechanism 方向一致性进入 gap。
2. `_score` 把 `evidence_against`/机制 confidence/`expected_direction` 纳入 `evidence_quality` 或单独 penalty；低于 0.40 的混合机制不得生成 regime 候选（至少降为 low_priority）。
3. `apply_lifecycle`（当前已修）重扫后确认 OPP-0002 被 invalidated；`catalyst`（当前已修）重扫后确认 QQQ/SPY/N225 掉出 top-3。
4. `goe/validation.py` 的 `found_detectors` 改为 case 实体/机制范围，或把“全局检测”降级为辅助数据，不能作为 pass 条件。
5. handoff parser 读 `data.status`/L3/L4/L1 rows；`out_of_scope` 单独状态，不再记 partial；问题先过 B 的 4 类 registry，或明确标为“B out_of_scope，不交付”。

（本报告只写研究方法/交接判断；工程/数据修复建议以 `FINAL_QA_AUDIT.md` 和 issue ledger 为准。）
