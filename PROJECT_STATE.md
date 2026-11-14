# PROJECT_STATE — 项目状态（唯一权威进度记录）

> 最后更新：2026-11-15 02:05 HKT

## 0. 最新一轮（2026-11-15）：Release gate v3

| 项 | 状态 / 证据 |
|---|---|
| 分支 | `architecture/research-v2`（远程 HEAD `047918f`） |
| 修复提交 | `c0392de` → `3c3d03f` → `63e4afb` → `fe3867d` → `fccfa9f` |
| 测试 | **193 offline passed / 0 skipped / 10 deselected**（network 9 + realdata 1） |
| 测试证明 | `audit/test_evidence/20261114T180115Z_fccfa9fc20.proof.json`（schema v3） |
| 独立验证 | `python -m goe.cli verify-release --proof <proof>` → accepted，重放 193/193 |
| 移植性 | 全新 clone（6.9 MB，无 .venv）用外部解释器重放 → accepted |
| 红队轮 1 | 4 个攻击成功（P0×2：根目录伪 pytest、skip 计数），已全部修复；见 `audit/QA_REDTEAM_RELEASE.md` |
| 红队轮 2 | v3 复审（进行中） |
| 剩余风险 | 测试质量不可证、`.git/info/exclude` 隐藏本地文件、宿主级篡改、network/realdata 尚未纳入发布 |

**P1-01 / P1-02 状态：FIXED（工程层）。** 门禁不再接受调用方提供的 pytest 命令；已执行集合必须等于收集集合；
证明只含 `{python}`/`{junit}` 模板与仓库相对路径；发布清单必须重放整套测试后才生成。

**下一步**：红队轮 2 结论 → 若有 P0/P1 继续修复；之后处理 data/research 侧遗留项（见 `audit/FINAL_ACCEPTANCE.md`）。

---

> 历史更新：2026-11-14 11:20 HKT
> 更新规则：每次会话结束或关键阶段完成后更新；状态必须对应真实文件、测试结果与 git 提交。
> 恢复流程：读 `PROJECT_SPEC.md` → 本文件 → 检查 `git log` / `pytest` / `goe doctor` → 继续未完成项。

## 1. 当前阶段

**Phase 4：验证、审计与交付**（功能开发已完成；历史回放进行中；测试套件与事件日历由子 Agent 生成；
GitHub 远程仓库等待授权）。

## 2. 已完成（有可验证证据）

| 项 | 证据 |
|---|---|
| 项目骨架、配置体系（universe/curves/macro/positioning/themes/thresholds/scoring/cases） | `config/`、`goe/config.py`、`goe doctor` 输出 125 标的/4 曲线/16 宏观/16 仓位 |
| SQLite 存储与审计表 | `goe/db.py`（14 张表）、`data/goe.db` 约 120MB |
| 10 个数据源适配器（9 指标 + Yahoo 价格） | `goe/sources/*.py`、`docs/DATA_SOURCE_NOTES.md`、联网测试 9 项 |
| 价格回填 2015-2026 | 125 标的 / 358,310 行；最新完整 K 线 2026-11-12（11-13 美股盘中 bar 被丢弃） |
| 指标回填 2014-2026 | 92 序列 / 159,508 行（Treasury/MOF/ECB/ChinaBond/BLS/BIS/Eurostat/CFTC/Shiller） |
| 时点特征层（价格/曲线/信用/仓位/宏观/估值/广度/相关性） | `goe/features.py`；7.5 年窗口；宏观发布滞后；陈旧序列剔除 |
| 14 类异常检测器 + 限流去重 | `goe/anomalies.py`；live 扫描 2,935 条（200 天窗） |
| 15 条传导机制 + 评估器 | `config/mechanisms.yaml`（53 项检验）、`goe/transmission/evaluator.py` |
| 机会引擎（5 原型/评分/主题去重/生命周期） | `goe/opportunities.py`；live 扫描 15 个候选（2 deep_research, 11 watch, 2 low_priority） |
| 端到端管线与报告 | `goe/pipeline.py`、`reports/report_2026-11-13.md`、`reports/scan_2026-11-13.json` |
| 交接导出与适配器 | `goe/integration/`、`exports/pipeline_2026-11-13.json`、`exports/research_tasks/` |
| **与 investment-agent 实测联调** | `goe handoff` → `ia_cli.py research-run` rc=0, 7.32s, 产出 `exports/ia_runs/OPP-0001/.../report.md` |
| 只读仪表盘 | `goe/web/app.py`（`goe web`，未做浏览器像素级验收） |
| 历史案例配置 7 个 + 回放器 | `config/cases.yaml`、`goe/validation.py` |
| 官方事件日历 35 条（34 已核验） | `config/events.yaml`、`goe events --check` |
| 测试套件 93 项离线 + 9 项联网 | `tests/`（10 个文件）、`TEST_RESULTS.md` |
| 五类机会原型全部有触发测试 | `tests/test_archetypes.py` |

## 3. 进行中

| 项 | 状态 | 位置 |
|---|---|---|
| 历史案例回放（最终版） | 运行中（7 案例，最终代码） | `reports/validation_cases_*.md` |
| 独立 QA 审计 | ✅ 完成（两轮，含复审） | `docs/QA_AUDIT.md` |

## 4. 未完成 / 待办

1. 历史案例最终结果归档（`docs/examples/` + `docs/VALIDATION.md` 数字）。
2. 独立 QA 审计（数据准确性/传导逻辑/评分/前视偏差/代码质量/稳定性）。
4. `docs/DATA_SOURCES.md`、`docs/LIMITATIONS.md`、`docs/SCORING.md`、`docs/VALIDATION.md`、
   `docs/INTEGRATION_INVESTMENT_AGENT.md`、`TEST_RESULTS.md` 定稿。
5. 3 年时点回放（`goe replay`）完整跑一遍并归档结果。
6. 敏感信息扫描、`.gitignore` 检查、git 提交。
7. GitHub 远程仓库创建与推送（**阻塞**，见 §5）。
8. 最终验收表（PROJECT_SPEC §6）与提交哈希写入交付说明。

## 5. 阻塞问题

| 阻塞 | 影响 | 需要的动作 |
|---|---|---|
| ~~GitHub 远程仓库创建缺少 API 授权~~ | 已解除 | 用户提供 token 后创建私有仓库并推送；远程 `main` 与本地提交一致 |
| 无 | — | — |

## 6. 最近一次验证结果

- 2026-11-13 23:15（审计修复后）：`goe scan --no-ingest` 成功。125/125 标的可用；异常 2,935；
  机制 8 激活（6 mixed / 1 weak / 1 unsupported）；机会 15（deep_research 2、watch 10、low_priority 3）；
  报告与交接文件已重新生成；handoff 对新 OPP-0001 重新实测 rc=0（7.05s）。
- 2026-11-13 22:01：`goe handoff --limit 1` 成功（rc=0，7.32s），investment-agent 产出四层报告。
- 2026-11-13 22:55：`pytest tests -m "not network"` → 93 passed；`pytest tests -m network` → 9 passed。
- 2026-11-13 22:51：`goe events --check` → 35 条事件，34 条已核验，引用 id/日期全部有效。
- 2026-11-13 21:52：指标回填成功（159,508 行 / 36 targets / 0 failed / 20s）。

## 7. 已知限制（摘录，完整见 docs/LIMITATIONS.md）

- Yahoo 聚合层；期货连续合约未展期调整；信用利差为 ETF 代理。
- 美国以外无本地信用利差；无分析师预期、ETF 资金流、期权隐含分布、行业估值。
- Shiller CAPE 止于 2023-09、Eurostat 镜像止于 2025-12 → 系统判定陈旧并停用。
- 事件日历仅官方核验日期；中国社融/PMI/地产等未接入。
- 历史回放衡量检测能力，不代表投资收益。

## 8. 下一步行动（按序）

1. 收齐测试套件 → 运行 → 修复 → 记录 `TEST_RESULTS.md`。
2. 收齐事件日历 → 校验 id/日期 → 重跑扫描（含 catalyst）。
3. 完成案例回放 → 归档 → 更新本文档与 `docs/VALIDATION.md`。
4. 3 年回放 → 归档稳定性指标。
5. 独立 QA 子 Agent 审计 → 修复 → 复审。
6. 文档定稿 → 敏感信息扫描 → git 提交 → 请求 GitHub 授权 → 推送 → 核验远程一致。
7. ✅ 已推送 GitHub 私有仓库并核验远程一致：https://github.com/bojing951-hash/global-opportunity-engine

## 9. 交付信息

- 仓库：https://github.com/bojing951-hash/global-opportunity-engine （private）
- 分支：`main`
- 功能提交：`1a7a5f5c7f98710f017584a34a99c7799bc97d66`；其后的文档提交一并推送（HEAD 以 `git log -1 --format=%H` 为准）
- 独立 QA：`docs/QA_AUDIT.md` — PASS WITH MINOR ISSUES（两轮，3 个 blocker 已修复并复审）
- 历史案例：7/7（`docs/examples/validation_cases_2026-11-13.md`）
