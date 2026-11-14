# R3 最终验收 QA（第三轮，pass 3）

- 审计对象：`global-opportunity-engine`，当前 worktree（HEAD `6755d34` + 未提交修改）
- 审计时间：2026-11-14 17:16–17:40 HKT
- 权限：只读；除本文件外未修改仓库、DB、配置、测试或 git
- 原则：以当前 DB/`reports/`/`exports/`/`audit/*.md` 与当前代码为准，不以旧报告结论直接背书

## 0. 判决

**ENGINEERING ACCEPTED WITH ISSUES（无代码级 P0/P1，157 项离线测试 exit 0）；INVESTMENT RESEARCH CAPABILITY NOT VALIDATED；六门整包验收 NO-GO。**

原因不是“代码不能跑”，而是**最终验收证据与最终 DB 状态不一致**，存在 2 个验收级 P1：

1. **P1-R1 当前 DB 没有 handoff 的 `not_completed:refused` 记录。** `research_tasks` 只有 2 条
   `exported`（OPP-0002/0003）；`opportunity_events` 中 0 条 `ia_research_*`；当前库只有
   1 次 `scan-20261114T090844Z-52b0e7`。`FINAL_ACCEPTANCE.md` 却把 “task `not_completed:refused`”
   写成当前事实。真实拒绝只存在于 `exports/ia_runs/OPP-0001|0002/.../report.json` 的 S8
   `out_of_scope` 中，且这两份 artifact 是 16:35/16:43 的旧对象，当前 DB 无任务状态可对账。
2. **P1-R2 README/集成文档仍写 handoff 假成功。** `README.md:153` 与
   `docs/INTEGRATION_INVESTMENT_AGENT.md:108` 仍写 `OPP-0001: ok rc=0`，`docs/...:4.3` 标题仍是
   “实际执行深度研究（已验证）”。这与当前语义（refused / exit 2 / 未完成）直接矛盾，会让
   读者把 A→B 当作已成功交付。`PROJECT_SPEC.md:83` 仍写 `not_completed:partial`，也是旧状态。

因此：**工程可以继续；研究能力不能签收；六门不能整体签收。**

## 1. 逐项验证

| # | 检查项 | 当前证据 | 判定 |
|---|---|---|---|
| 1 | DAX 本地 driver 修复 | **当前 OPP-0004 已不是 DAX，而是 QQQ（`low_priority` 0.5142）**；11 个候选中无 DAX；queue 中无 DAX。用当前代码复算 DAX：drivers = `SX5E / DXY / UST10Y / EURUSD`（`_driver_returns`），生产 history_start=2020-05-15 得 z=1.991、R²=0.906、gap=0.327；换 history_start=2020-06-11 得 z=1.383、gap=0。**原始“DAX 假 watch”已通过“DAX 不入候选”解决；但“gap≈0”不具备样本相位稳健性，不能写死为事实。** | 原 P1-1 **已修复（以排除方式）**；文档“DAX low 0.514”见 #6 |
| 2 | 研究队列 | `exports/research_queue_2026-11-13.json` 只有 OPP-0002、OPP-0003 两条 `watch`，priority 1/2；无 `low_priority`/priority 1。`pipeline_2026-11-13.json` 仍保留 3 个 low：OPP-0001 0.6034、OPP-0004 0.5142、OPP-0005 0.4875。导出代码 `if row["status"] not in ("deep_research","watch","new"): continue`，low 不会进 queue（允许 `new` 是轻微口径差异，当前无实例）。 | **PASS** |
| 3 | 盲评/前瞻诚实性 | `audit/RESEARCH_QUALITY.md`：C 引擎 **1.188** < A 价格 **1.312** < B 异常 **1.521**；P@3 0.417/0.500/0.750；分项 C 的 falsifiable/data_sufficiency 更低；结论明确“不能支持引擎优于简单排行榜”。前瞻：C +7.12% 但 ex-top **+2.45%**、class-relative +2.99%、beat-class 42%；B +5.09/ex-top +1.05/class +5.42/58%；FXI 贡献约 4.9pp。**没有宣称优势，数字与 mapping/ratings 口径一致。** | **PASS（诚实披露）** |
| 4 | Handoff | 代码/测试层：`cmd_handoff` 非 `ok_valid` 返回 2；`run_task` 清空 out_dir、`min_mtime` 拒绝陈旧；`parse_research_artifact` 对 L2-only/空 evidence 返回 insufficient；`test_readiness_handoff.py` 有 ok_valid/refused/rejected/insufficient/partial/missing/stale/L2-only 与 rc17/stale 用例。真实 artifact：OPP-0001、OPP-0002 的 S8 均 `out_of_scope`（refused 证据成立）。**但当前 DB 无 `not_completed:refused` 任务、无 `ia_research_not_completed` 事件，只有 2 条 exported。** | 语义/测试 **PASS**；当前验收状态 **FAIL（P1-R1）** |
| 5 | P1-A/P1-B/P1-2/P1-3 | 当前扫描 `data_readiness.ok=true`、`critical=[]`、`degraded=true`（EA_HICP 347d），无 blocked；1506 异常、11 候选、5 机制（2 mixed/3 unsupported）。测试存在：`test_data_integrity.py`（历史 bar/split/level_rebased）、`test_features.py`（PIT/stale macro）、`test_readiness_handoff.py`（市场/曲线/宏观/盘中 bar/1-125 provider/隐式 wall-clock），`test_pipeline_e2e` 回滚。工程 QA 矩阵已覆盖 1a–7；本轮 spot-check 未见回归。**未重新跑完整 build(t) vs build(T).slice(t) 8.8M 行属性测试，接受工程 QA 的冻结哈希结论**（该报告已注明 split 当日 P2-1）。 | **PASS（有 P2 残留）** |
| 6 | 文档 vs DB | DB：1506 异常、11 候选 = 2 watch/3 low/2 invalidated/4 excluded、0 deep；top 分 DXY 0.5927、N225 0.5577（注：按分数第一是 OPP-0001 low 0.6034）；125 标的、358,310 价格、159,508 指标；测试 157。**仍有过期数字**：`FINAL_ACCEPTANCE.md:53/62` 写 “DAX low 0.514” 与 “DAX dropped from watch 0.529→low 0.514”，实际 DAX 不在 11 候选；`VALIDATION_RESULTS.md:39` 同样写 DAX low 0.514；`TEST_RESULTS.md` §6 仍写 “make test # 89 passed”；`EXECUTION_STATE.md` “Completed this round” 仍写 121 tests/3 watch/2 low/1 invalidated/5 excluded；`docs/SCORING.md:77-89` 仍以 OPP-0001 0.606 watch 举例；`PROJECT_SPEC.md:83` handoff 仍写 partial；`README.md:153`/`docs/INTEGRATION...` 仍写 `ok rc=0`。 | **FAIL（P1-R2 + 多处 P2 旧数）** |
| 7 | 离线测试 | `.venv/bin/python -m pytest tests -m "not network" -q`：**exit 0**；工程 QA/当前文档口径 **157 passed, 9 deselected**（本轮复跑未打印汇总行，但套件通过、耗时约 75s）。 | **PASS** |
| 8 | 新 P0/P1 | 未发现新的代码级 P0/P1（无伪造、无前视、无扫描阻断回归）；但发现 2 个验收级 P1（R1/R2）。 | 代码 **PASS**；验收 **NO-GO** |

## 2. 六门状态

| Gate | 状态 | 依据 | 反证/保留 |
|---|---|---|---|
| 1 Data | PASS with residuals | 当前 readiness ok/degraded，125/125；bar 完整性与 PIT 测试在；CSI300 复算 4017.855；历史 build/slice 一致（工程 QA） | split 当日 P2-1；CFTC/BLS/BIS 真实 vintage 未核实；futures roll 仅标记 |
| 2 Quant | PASS with residuals | 独立复算 SPY/CFTC/CPI/UST；VIX 5y 分位差约 0.005；无新前视 | HAC p 值、同源价格重复计分、crypto/equity 窗口标签差异 |
| 3 Engineering | **PASS** | 157 离线测试；事务回滚；detector/ingest 阻断；handoff 代码 exit 2；当前 scan success | P2：split 当日、schema 残留、lab mode、报告 100% 与 partial 并列 |
| 4 Methodology | PARTIAL | 过去政策不再当前置 catalyst；>10 天降级；失效检查；本地 driver（DAX 无 DE 时落 SX5E/EUR） | **DAX gap≈0 对样本起点敏感（z 1.38–1.99，gap 0–0.33）**；proxy 非一致预期/期权；只有首个 trigger 自动失效 |
| 5 Discovery | **NOT VALIDATED** | 严格 PIT replay 7/7；当前 2 watch/0 deep；blind r3 引擎 1.188 最后；forward ex-top 2.45% < B 5.09%，beat-class 42% < 58% | 无人类标签、n=12、事实卡机制不对称；**不能宣称研究优势，也不应把“0 deep”当质量结果** |
| 6 Integration/QA | **PARTIAL / NO-GO** | parser 语义正确、exit 2、测试齐全；真实下游 refused 有 artifact | **当前 DB 无 not_completed:refused；README/集成文档仍写成功；无真实 ok_valid；B 零模型 intent gate 拒绝资产问题** |

## 3. 最强反证（为什么不能签收）

1. **最终 DB 与最终验收文字互相打架**：验收说 handoff 记录了 `not_completed:refused`，当前库只有两条 `exported`，没有任何 IA 事件；32 个 `research_tasks` 文件里也只有 2 个进入 queue。审计者按最终 DB 无法复现“refused/exit 2”这一关键结论。
2. **用户可见文档仍把失败写成成功**：README 和集成文档的 `ok rc=0` 是整条 A→B 链上最容易被误读的一句话；它比一份内部 P2 更严重，因为它直接改变验收者的判断。
3. **DAX 的“修复”是排除，不是“gap≈0”**：当前候选确实没有 DAX，但用当前代码复算 DAX 仍得到正 gap（生产 history_start 下 0.327，z=1.991）；“gap≈0/low 0.514”是旧扫描在特定样本相位下的结果，不能作为最终事实写入验收。
4. **盲评方向明确对引擎不利**：C 1.188 < B 1.521、< A 1.312；前瞻 ex-top +2.45% < B +5.09%，beat-class 42% < 58%。这支持“研究能力未验证”，不支持任何“引擎更优”的表述。
5. **当前只有 2 个 watch、0 个 deep**：按分数第一还是 OPP-0001 的 28 天前政策 low（0.6034）；“top-3 独立前瞻”不成立。

## 4. 结论与建议

- **工程层**：接受（PASS WITH ISSUES）。无代码级 P0/P1；157 测试 exit 0；扫描/readiness/事务/parser 未发现回归。
- **研究层**：不接受。盲评 r3 引擎最后、前瞻无稳健优势、0 deep、无人类标签。
- **验收层**：**NO-GO**。先修 P1-R1（把真实 handoff 的 `not_completed:refused` 写入当前 DB，或明确最终验收以哪份 DB 快照为准并冻结该快照）与 P1-R2（README/集成文档删掉 `ok rc=0` 假成功，改成 refused/exit 2/未完成）；同时清理 #6 的 DAX 0.514、89/121/137 等旧数。修完后可把工程签收为“ACCEPTED WITH ISSUES”，但研究能力仍需外部专家/前瞻验证，不能靠再改代码制造。

> 本报告只写结论与证据，未修改代码、DB、配置、测试或 git；唯一写入即本文件。
