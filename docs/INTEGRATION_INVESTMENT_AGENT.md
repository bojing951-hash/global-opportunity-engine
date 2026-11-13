# INTEGRATION — 与既有 investment-agent 的对接

> 目标：让已有的深度研究系统知道**接下来最值得研究什么**，同时不修改、不替换、不破坏它。

## 1. 对接检查结果（2026-11-13）

| 项 | 实际情况 |
|---|---|
| 仓库 | `~/investment-agent-dev`（GitHub `bojing951-hash/investment-agent` 本地开发树） |
| 入口 | `ia_cli.py`（约 89KB，统一 CLI） |
| 子命令 | `doctor / update / overview / changes / history / compare / research / analog / archive / views / research-map / research-run / research-attach` |
| 研究入口 | `research-run --question "<text>" [--out-dir DIR] [--fanout]`：11 步确定性管线，零模型 |
| 数据 | `data/daily|weekly|news|research|institutions`；SQLite/JSON 混合，本引擎只读不写 |
| 运行环境 | 系统 `/usr/bin/python3`（其依赖已安装）；无独立 venv |
| 输出 | 四层研究报告（事实/机构观点/AI 推断/情景），L3/L4 标记为 `declared-not-produced`，由人工/Agent 补作 |

结论：**存在稳定、可脚本化的研究入口**，不需要修改其核心代码。

## 2. 集成架构

```
goe                            exports/                              investment-agent
────────────────────────────── ──────────────────────────────────── ────────────────────────────
opportunities (SQLite)
  │
  ├─ pipeline_<date>.json  ──►  完整机会管线（含证据/机制/问题）   （被外部工具消费/审计）
  ├─ research_tasks/RT-*.json ─► 单个自包含研究任务（question + context）
  ├─ research_queue_<date>.json ► 优先级队列 + 建议命令
  └─ HANDOFF_SCHEMA.json   ──►  JSON Schema（版本化）
                                        │
                                        ▼
                              goe handoff
                              ia_adapter.build_research_question()
                              ia_cli.py research-run --question ... --out-dir ...
                                        │
                                        ▼
                              exports/ia_runs/<OPP-ID>/<ts>_<slug>/{report.md,report.json}
```

**设计原则**

1. 适配器模式：本引擎只生成标准 JSON 与命令行调用，不 import 对方内部模块、不写对方仓库。
2. 输出目录显式传入（`--out-dir`），默认落在本仓库 `exports/ia_runs/`，避免污染对方目录。
3. 研究问题必须**自包含**：深度研究系统只看到一段文字，因此现象、假设、证据、失效条件、
   待回答问题、请完成事项全部嵌入。
4. 状态回写可选：`research_tasks` 表与 `opportunity_events` 记录调用结果；不影响对方内部状态。

## 3. 交接文件格式（HANDOFF_SCHEMA v1.0）

`exports/pipeline_<date>.json`：

```json
{
  "schema_version": "1.0",
  "engine": {"name": "global-opportunity-engine", "version": "0.1.0",
             "scan_id": "scan-...", "as_of": "2026-11-13", "generated_at": "..."},
  "provenance": {"config_hash": "...", "data_hash": "..."},
  "summary": {"n_opportunities": 18, "by_status": {...}, "by_archetype": {...}},
  "opportunities": [ <envelope>, ... ]
}
```

`envelope.opportunity` 必备字段：

| 字段 | 说明 |
|---|---|
| `opportunity_id` / `fingerprint` | 稳定标识（可跨日追踪同一现象） |
| `status` / `score` / `score_breakdown` | 研究状态与可解释评分 |
| `archetype` / `title` / `market` / `asset_class` / `horizon` | 分类与时间窗口 |
| `instruments` | 标的（id/名称/代码/角色） |
| `discovery` | 发现了什么、为什么现在、待检验假设、异常列表、上下文判定 |
| `mechanism` | 机制 id、链条、置信度、成立条件、识别状态（相关≠因果） |
| `evidence_for` / `evidence_against` | 支持/反对证据（含来源、层级、as_of、强度） |
| `catalysts` | 已核验事件（日期/类型/来源） |
| `open_questions` | 需要深度研究回答的问题 |
| `invalidation` | 初步假设失效条件 |
| `data_quality` | 数据质量分与缺口 |
| `research_question` | 直接传给 `research-run` 的完整问题文本 |

`research_tasks/RT-<date>-<seq>.json` 额外包含 `task_id / priority / expected_outputs / callback`，
其中 `callback.status_map` 约定：`accepted → deep_research`、`deferred → watch`、`rejected → excluded`。

## 4. 使用方法

### 4.1 只导出，不调用

```bash
.venv/bin/python -m goe.cli scan                # 自动写 exports/
.venv/bin/python -m goe.cli export --out exports/
```

### 4.2 生成研究问题（不执行）

```bash
.venv/bin/python -m goe.cli handoff --ia-path ~/investment-agent-dev --limit 2 --dry-run
```

### 4.3 实际执行深度研究（已验证）

```bash
.venv/bin/python -m goe.cli handoff --ia-path ~/investment-agent-dev --limit 1
```

实测输出（2026-11-13）：

```
investment-agent: ~/investment-agent-dev exists=True cli=True python=/usr/bin/python3
OPP-0001: ok rc=0 elapsed=7.32 out=.../exports/ia_runs/OPP-0001
```

生成文件：

```
exports/ia_runs/OPP-0001/20261113T140140Z_.../report.md
exports/ia_runs/OPP-0001/20261113T140140Z_.../report.json
```

`report.md` 开头即包含本引擎生成的研究问题（现象/假设/传导逻辑/支持与反对证据/失效条件/需要回答），
随后是 investment-agent 自己的四层报告（事实层、机构观点层、AI 推断层标记未产出、条件情景层）。

### 4.4 批量/定时

```bash
# 每日扫描后只研究 top 3，写入 exports/ia_runs，然后人工复核 report.md
.venv/bin/python -m goe.cli handoff --ia-path ~/investment-agent-dev --limit 3
```

建议不要自动把深度研究结果当作决策：`deep_research` 候选需要研究员复核证据链后再进入其流程。

## 5. 与对方研究问题库的关系

对方 `config/research_questions.json` 是章程十问（RQ1–RQ10），属于其治理文件。
本引擎**不覆盖**它，只提供追加提案：

```bash
.venv/bin/python -m goe.cli handoff --ia-path ~/investment-agent-dev --limit 3 \
  --question-patch exports/ia_question_patch.json
```

提案格式：

```json
{"schema_version": "1.0", "merge_mode": "append",
 "target_file": "config/research_questions.json",
 "append": [{"id": "GOE-OPP-0001", "text": "...", "primary_layer": "AI推断",
             "draws": ["客观事实", "历史统计"], "surface": "goe opportunity ..."}]}
```

由使用者（或对方项目自己的工具）决定是否合并；本引擎不直接写对方仓库。

## 6. 失败与降级

| 场景 | 行为 |
|---|---|
| `--ia-path` 不存在 | `IAAdapter.check()` 返回 notes；`handoff` 打印原因并退出（不伪造成功） |
| `ia_cli.py` 缺失或 CLI 变更 | `check()` 检测 `research-run` 是否存在；缺失则拒绝执行 |
| 研究运行超时/非零退出 | 返回 `status=failed/timeout`，保存 stdout/stderr 尾部，便于诊断 |
| 未安装/无网络 | 导出文件仍完整生成；深度研究可在有环境时再执行 |

## 7. 边界

- 本引擎不读取对方的私有数据；不把对方内部结论写入本仓库。
- 不修改对方代码/配置/数据；不向其数据目录写入。
- 本引擎的评分与机会是研究线索，不是交易建议；对方系统负责估值、赔率与决策。
- 双方通过**文件 + CLI**解耦，任一方升级不会隐式破坏另一方；接口变更需更新
  `HANDOFF_SCHEMA.json` 的 `schema_version` 并记录在 `DECISIONS.md`。
