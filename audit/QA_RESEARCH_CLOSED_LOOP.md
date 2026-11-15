# N225 研究闭环最终独立 QA（HEAD c849701 / code 8266fa6）

- 分支：`architecture/research-v2`
- 审计对象：`research_results/2026-11-13/N225/*`、`goe/research_exec.py`、`goe/cli.py`、DB 写回
- 审计时 HEAD：`c849701`（代码自 `8266fa6` 起未变；`c849701` 仅新增 release/QA 文档）
- 结论：**A–E 全部 PASS；P0 = 0，P1 = 0；闭环接受（ACCEPTED），非有条件接受。**
- 仅只读核验；本文件为唯一新增文件，未改代码/数据/artifact。

## 1. 核心事实核验

| 项 | 证据 | 结果 |
|---|---|---|
| 前一美股 session | `observed.US_*` / `GX_*` 的 `data_date=2026-11-05`，`alignment=prior_us_session`；`tests.json.global_lead_test.prior_us_session=2026-11-05` | PASS |
| 同日美股未使用 | 11-06 实际 SPY +0.31%、QQQ +1.40%、VIX -9.01%，artifact 与代码均未采用；`learned` 明写同日收盘是 lookahead | PASS |
| H-GLOBAL 一致 | 11-05 SPY -4.41%、QQQ -6.49%、VIX +69.66%，H-EQJP-GLOBAL = `SUPPORTED_BY_AVAILABLE_EVIDENCE`；措辞为 consistent/association，非因果 | PASS |
| Local / 北亚 | TOPIX -6.50% < -3%；TAIEX -4.51%、KOSPI -6.02% 均 < -3%；`tests.json` 两项 pass=True | PASS |
| Finding 状态 | `status=INCONCLUSIVE`；local 与 regional 并存，broad indices 无法区分；无 alpha/mispricing | PASS |
| 无 stale 矛盾/科技过度归因 | 全文无 “US-global contradicted”；仅 “consistent, not contradicted”；tech 明写 `not identified`；HSI -1.27%/CSI -1.44% 已写入 `learned`，口径收窄为 North Asia | PASS |

DB 原始 close 独立复算与 artifact 一致：N225 57434.77/61077.90 = -5.9647%；SPY 733.00/766.81 = -4.4092%；VIX 28.18/16.61 = +69.6568%；USDJPY -0.0707%。

## 2. 验收 A–E

| 验收 | 判定 | 证据 |
|---|---|---|
| A 证据获取 | **PASS** | `evidence.json`：来源 `GOE prices DB`、逐资产 data_date、`data_hash=55e06c14…`、`input_rows=780`；`finding.json.input_sha256=1ba5745e…`；DB 最大价格日期 2026-11-13 = as_of，无未来 bar |
| B 实际检验 | **PASS** | `tests.json` 5 项检验均有显式规则/阈值；`goe/research_exec.py` 实现与 `finding.json.rules` 一致：local/regional `< -3%`、global `SPY < -1% 且 VIX return > 0`、fx `|USDJPY| >= 20%*|N225|`、reversal 3 日累计 > 0；同日美股排除已固化 |
| C 假设更新 | **PASS** | DB `research_v2_hypotheses` 已持久化 8 条：LOCAL/GLOBAL/ASIA-REGIONAL=SUPPORTED，FX=WEAKENED，POLICY/FUND=INSUFFICIENT_DATA，POS/ART=untestable；`research_v2_findings` payload 与 `finding.json` 逐字段相等 |
| D Finding | **PASS** | `findings.md`/`finding.json`：INCONCLUSIVE、数值完整、still_unknown/next_action 齐全、`DISCOVERY VALUE: NOT VALIDATED`、不向 B 交接未支持研究 |
| E 独立 QA | **PASS** | 先有 `QA_RESEARCH_EXECUTION.md`、`QA_RESEARCH_EXECUTION_2.md`（已在 c849701 跟踪）；本轮独立复核 A–E，并关闭上一轮 2 个工程 P1 |

## 3. 可复现性与测试

- `8266fa6` 为 HEAD 祖先，`git ls-tree 8266fa6` 含 `goe/research_exec.py`、`goe/cli.py`、`goe/db.py`、`tests/test_research_exec.py` 及 `research_results/2026-11-13/N225/*`；`git diff 8266fa6..c849701 -- goe tests` 为空，代码可复现。
- 用 DB 副本重跑 `python -m goe.cli research-case --as-of 2026-11-13 --out /tmp/qa_n225 --db /tmp/qa_goe.db`：`evidence.json`、`tests.json`、`plan.json` 完全相同；`finding.json` 除 `code_commit`（运行时 HEAD）外所有字段相同。CLI 可复现。
- `python -m pytest`（默认 marker `not network and not realdata`）exit 0；收集 241 项、241 通过；CI run 31 green（lead 提供，与本地一致）。

## 4. P0/P1

- **P0：0。** 未发现伪造价格、未来数据、伪造政策日期或 consensus。
- **P1：0。** 上一轮两个 P1 均已关闭：
  1. provenance：`8266fa6` 已含 research_exec/CLI/DB/tests 与 artifacts，finding 记录的 commit 可运行；
  2. 测试：`tests/test_research_exec.py` 已覆盖 prior-session 选择、同日美股排除（spy_return 断言）、DB hypotheses/findings 写回，CI 可见。
- 方法论无 P1：PIT 对齐、规则/阈值一致、finding 与 DB 一致、结论口径 INCONCLUSIVE 均成立。

## 5. 仅 P2/P3（不阻塞）

- **P2**：`ACCEPTANCE.md` 的 E 行仍写 `pending / see report`，未随 QA 落地更新；建议改为 PASS 并引用本文件。
- **P2**：单测只直接回归 global 规则 + lag + DB；local/regional/fx/reversal 阈值与 reversal 边界无独立用例（实现简单、本轮人工核对通过）。
- **P2**：`code_commit` 取运行时 HEAD，换 commit 重跑会写入新 SHA；精确复现需 checkout `8266fa6`。建议 artifact 另记代码 blob hash 或固定 commit。
- **P2**：DB `research_v2_findings.created_at=2026-11-15T11:34:43Z` 为首插时间，upsert 不更新、无 updated_at；candidate 仍 `intelligence`，finding 已出但生命周期未推进。
- **P3**：`H-ASIA` 仅为 ACCEPTANCE 简称，DB 实际 id 为 `H-EQJP-ASIA-REGIONAL`；建议统一命名。
- **P3**：fx 的 20% 相对阈值无敏感性分析；`H-EQJP-GLOBAL` 用 SUPPORTED 而 learned 用 consistent，强度措辞可再收紧（finding 已 INCONCLUSIVE，不构成误导）。

## 6. 最终判定

**接受（ACCEPTED）。** N225 研究闭环 A–E 全部通过：PIT 正确（prior-US 2026-11-05）、同日美股排除、local 与 North Asia 支持、H-GLOBAL 一致、finding INCONCLUSIVE 且无科技过度归因；假设与 finding 已落库；`8266fa6` 可复现；241 测试通过。无 P0/P1，仅余上述 P2/P3 文档与生命周期改进项。
