# AGENT_TASKS — 多 Agent 分工、依赖与完成记录

> 本文件记录真实的任务分派与结果。本项目使用 DeepSeek Harness 的 subagent 能力实际调用子 Agent；
> 未调用子 Agent 的工作由 Chief Agent（主 Agent）完成。所有"完成"均对应仓库中的真实文件与可复现命令。
>
> 最后更新：2026-11-13 23:00 HKT

## 0. 团队与职责

| Agent | 角色 | 负责范围 | 实际执行 |
|---|---|---|---|
| Agent 0 | Chief / Lead | 需求拆解、架构、核心代码、整合、验收、GitHub | 主会话（`lead`） |
| Agent 1 | Data Engineering | 数据源调查、适配器、历史回填、数据质量 | 子 Agent `data-engineer` |
| Agent 2 | Global Macro & Cross-Asset | 传导机制库、方法论文档 | 子 Agent `macro-transmission` |
| Agent 3 | Opportunity Detection | 异常检测、机会生成、评分、队列 | Agent 0 实现（与 Agent 2 交付的机制库对接） |
| Agent 4 | Integration | investment-agent 接口与适配器 | Agent 0 实现 + 实测联调 |
| Agent 5 | Software Engineering | 架构、CLI、存储、报告、仪表盘、调度 | Agent 0 实现 |
| Agent 6 | Independent QA & Research Reviewer | 独立审计（数据/逻辑/评分/前视/代码/稳定性） | 子 Agent `qa-auditor`（待启动） |
| — | Test Engineering（Agent 5 子任务） | 完整测试套件 | 子 Agent `test-engineer`（进行中） |
| — | Event Calendar Research | 官方事件日历核验 | 子 Agent `event-calendar`（进行中） |

## 1. 任务台账

| ID | 任务 | 输入 | 输出 | 依赖 | 状态 | 证据 |
|---|---|---|---|---|---|---|
| T-01 | 环境勘察（OS/Python/GitHub/数据源/子 Agent 能力） | 用户指令 | 环境结论 | — | ✅ 完成 | 本文件 §2 |
| T-02 | 检查 investment-agent 结构与接口 | 本地仓库 | 接口结论：`ia_cli.py research-run --question --out-dir` | T-01 | ✅ 完成 | `docs/INTEGRATION_INVESTMENT_AGENT.md` |
| T-03 | 项目规范与架构文档 | 用户指令 §4-§13 | `PROJECT_SPEC.md`、`ARCHITECTURE.md`、`DECISIONS.md` | T-01 | ✅ 完成 | 仓库根目录文件 |
| T-04 | 配置体系（125 标的/4 曲线/16 宏观/16 仓位） | 用户覆盖范围要求 | `config/*.yaml` + 校验器 | T-03 | ✅ 完成 | `goe doctor` |
| T-05 | 存储层（SQLite 14 表 + Store API） | 架构 | `goe/db.py` | T-03 | ✅ 完成 | 单元测试（待并入测试套件） |
| T-06 | 价格接入（Yahoo，125 标的，2015-2026） | universe | `goe/sources/yahoo.py` + 358,310 行 | T-04,T-05 | ✅ 完成 | `prices` 表统计 |
| T-07 | 指标接入（9 个 provider） | 曲线/宏观/仓位配置 | `goe/sources/{...}.py` + 159,508 行 | T-04,T-05 | ✅ 完成（子 Agent 1） | `docs/DATA_SOURCE_NOTES.md`、`pytest` 20 passed |
| T-08 | 时点特征层 | 价格+指标 | `goe/features.py` | T-06,T-07 | ✅ 完成（Agent 0） | 扫描输出、`no_lookahead_diff` |
| T-09 | 异常检测（13 类） | 特征层 + 阈值 | `goe/anomalies.py` | T-08 | ✅ 完成（Agent 0） | live 扫描 2,935 条 |
| T-10 | 传导机制库（15 条/53 检验）与方法论 | 用户 §A3 | `config/mechanisms.yaml`、`docs/TRANSMISSION_METHOD.md` | T-04 | ✅ 完成（子 Agent 2） | 子 Agent 校验：0 个未知 id |
| T-11 | 传导评估器 | 机制库 + 异常 | `goe/transmission/evaluator.py` | T-09,T-10 | ✅ 完成（Agent 0） | live 扫描 8 条激活 |
| T-12 | 机会引擎（5 原型/评分/去重/生命周期） | 异常+机制+事件+配置 | `goe/opportunities.py` | T-09,T-11 | ✅ 完成（Agent 0） | 14 个候选 |
| T-13 | 端到端管线与报告 | 全链路 | `goe/pipeline.py`、`goe/reports.py` | T-12 | ✅ 完成（Agent 0） | `reports/report_2026-11-13.md` |
| T-14 | 交接导出与 investment-agent 适配器 | 机会档案 | `goe/integration/*` | T-12 | ✅ 完成（Agent 0） | `exports/pipeline_*.json`、实测 rc=0 |
| T-15 | CLI 与安装/调度脚本 | 全链路 | `goe/cli.py`、`Makefile`、`scripts/` | T-13 | ✅ 完成（Agent 0） | `goe --help` |
| T-16 | 只读仪表盘 | Store | `goe/web/app.py` | T-13 | ✅ 完成（Agent 0） | `goe web` 可启动 |
| T-17 | 历史案例配置与回放器（7 案例） | 用户 §11 | `config/cases.yaml`、`goe/validation.py` | T-13 | ✅ 完成（7/7） | `docs/examples/validation_cases_2026-11-13.md` |
| T-18 | 完整测试套件（97 离线 + 9 联网） | 代码接口 | `tests/`（10 文件） | T-05..T-16 | ✅ 完成（子 Agent `test-engineer` + Agent 0 补充原型测试） | `TEST_RESULTS.md` |
| T-19 | 官方事件日历（35 条，34 已核验） | 官方来源 | `config/events.yaml` | T-04 | ✅ 完成（子 Agent `event-calendar`） | `goe events --check` |
| T-20 | 独立 QA 审计（两轮） | 全部交付 | `docs/QA_AUDIT.md` | T-18,T-19 | ✅ 完成（PASS WITH MINOR ISSUES） | 修复 3 个 blocker 后复审通过 |
| T-21 | 文档定稿与验收表 | 全部 | README、LIMITATIONS、TEST_RESULTS 等 | T-18..T-20 | 🟡 进行中 | — |
| T-22 | 敏感信息扫描 + Git 提交 | 仓库 | commit | T-21 | ⬜ 待做 | — |
| T-23 | GitHub 私有仓库创建与推送 | 远程授权 | remote URL + commit hash | T-22 | 🔴 阻塞（无 API 授权） | PROJECT_STATE §5 |

## 2. 环境勘察结论（T-01）

| 项 | 结论 |
|---|---|
| 系统 | macOS 15.6.1 / arm64 / 460GB 磁盘（可用 226GB） |
| Python | 系统 3.9.6（EOL，包混杂）；项目使用 uv 管理的 3.12.13 + `.venv` |
| Node | v24.13.1（本项目未使用） |
| Git | 2.50.1；`user.name=bojing951-hash`，`user.email=bojing951@gmail.com` |
| GitHub | SSH 认证成功（`git@github.com` → `bojing951-hash`）；`gh` CLI 未安装；无 PAT；`global-opportunity-engine` 仓库不存在 |
| 子 Agent | DeepSeek Harness subagent 可用；已实际调用 3 次（data-engineer / macro-transmission / event-calendar / test-engineer） |
| 网络 | Yahoo、Treasury、MOF、ECB、BLS、BIS、Eurostat、CFTC、CBOE、akshare(部分) 可用；FRED 超时；eastmoney 部分被阻断 |
| investment-agent | `~/investment-agent-dev`（本地开发树，公开仓）；CLI 12 个子命令；`research-run` 可执行（系统 python3） |

## 3. 子 Agent 交付记录

### Agent 1 — data-engineer（完成）
- 交付：9 个 indicator provider + 29 项测试（20 离线 + 9 联网）+ `docs/DATA_SOURCE_NOTES.md`。
- 实测：159,508 行 / 92 序列 / 0 失败 / 20s；覆盖 2014-2026。
- 发现并上报 5 个接口问题；主 Agent 已修复 3 个（http tuple|set、BIS 单位量纲、`:oi` 系列元数据）。
- 限制：akshare 内部 HTTP 无法走共享客户端（已捕获异常）；Eurostat 镜像止于 2025-12；Shiller 止于 2023-09。

### Agent 2 — macro-transmission（完成）
- 交付：15 条机制（53 项检验：40 corr + 13 conditional_return）、`docs/TRANSMISSION_METHOD.md`。
- 校验：所有引用 id 存在（0 unknown）；47 条参考文献，41 条有 URL，34 个唯一 URL 经 HTTP 核验；
  6 项无 URL 的文献不伪造链接。
- 缺口：无 DFII10/T10YIE、无 BAML OAS、无原油期限结构与库存、无中国高频数据——已写入机制 `required_data`。

### Agent 5（子任务）— test-engineer（完成）
- 交付：9 个测试模块 + conftest，89 项离线测试全部通过；发现并修复 3 个源代码缺陷（稳健 z 的 MAD、跨日去重保留最高分、机制相关窗口换算）。
- 主 Agent 追加 4 项原型触发测试（`test_archetypes.py`），当前 97 项离线 + 9 项联网全部通过。

### 研究（子任务）— event-calendar（完成）
- 交付：35 条事件（2026-11-20 → 2027-06-17），34 条官方核验、1 条中国 LPR 约定规则标记未核验；引用 id/日期校验通过。

### Agent 6 — qa-auditor（待启动）
- 任务：独立审计数据准确性、来源可靠性、传导逻辑、评分方法、前视/数据泄漏/幸存者偏差、代码质量、稳定性。

## 4. 依赖关系

```
T-01 → T-02 → T-03 → T-04 → {T-06, T-07} → T-08 → T-09 → T-11 → T-12 → T-13 → {T-14, T-15, T-16}
                                                              ↑
                                                     T-10 (机制库)
T-13 → T-17 (回放) / T-18 (测试) → T-20 (QA) → T-21 → T-22 → T-23
T-04 → T-19 (事件日历) → 重跑 T-13
```

## 5. 说明

- 本项目的"多 Agent"是真实调用：子 Agent 拥有独立上下文、独立工具执行，产出真实文件；
  未使用子 Agent 的部分由主 Agent 直接实现，不做角色扮演式虚构。
- 子 Agent 之间存在文件级隔离（各自只写指定文件），避免并发覆盖；主 Agent 负责最终整合与复审。
