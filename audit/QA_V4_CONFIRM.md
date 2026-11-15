# V4 最终确认 QA（HEAD 0dd9ce4 / code 24bdf13 / proof d199fb3）

- 审计对象：`global-opportunity-engine`，HEAD `0dd9ce4`（code `24bdf13`，proof `d199fb3`），249 tests，CI run44 SUCCESS（外部证据）
- 方法：只读静态审阅 + 只读 artifact/DB 核对 + 定向 pytest；仅写本文件，未改代码/配置/测试/DB
- 环境：2026-11-16，`git status --porcelain` 为空；工作副本干净

## 总判定

**通过（PASS）**：无 P0、无 P1。V4 可签署。

| # | 检查项 | 结论 | 证据 |
|---|---|---|---|
| 1 | FX/商品缺失 SPY/VIX → INSUFFICIENT_DATA | **PASS** | `24bdf13` 将 FX `H-FX-RISK`（`goe/research_engine.py:256`）与商品 `H-CMD-RISK`（`:296`）改用三态 `hs(...)`，`pass=None` 返回 `INSUFFICIENT_DATA`；新增回归 `tests/test_research_contract.py:71` 同时覆盖 `fx_level`/`commodity_event`，通过。 |
| 2 | 事件合同 TAIEX/KOSPI 确定性 | **PASS** | 最新 artifact：TAIEX `event_start=event_end=2026-11-06`、`price_return_shock/down`；KOSPI `2026-10-15`、`drawdown_extreme/deep_drawdown`；均由 `resolve_event` 精确绑定，缺事件抛 `EventNotResolved`（`tests/test_research_contract.py:25`），无静默漂移。 |
| 3 | 249 tests / proof | **PASS** | proof `audit/test_evidence/20261115T162532Z_d199fb3e47.proof.json`：`passed=249`、`failed=0`、`errors=0`、`skipped=0`、`exit_code=0`，`git_commit=d199fb3`、`git_dirty=false`；log/junit SHA256 已记录。 |
| 4 | CI run44 | **PASS（外部证据）** | 请求方记录 CI run44 于 HEAD `0dd9ce4` 绿色；仓库内 proof 与本地定向测试一致，未发现反证。 |
| 5 | 无 P0/P1 | **PASS** | 未发现阻断项；V4-FINAL 的 P1-1（FX/商品缺失被落为 WEAKENED）已由 `24bdf13` 修复并有专项回归。 |

## P0

无。

## P1

无。

## P2（不阻断）

- TAIEX 候选 payload 仍缺 `event_date/detector_id/direction`，事件绑定依赖 `observed_phenomenon` 文本 + 最近匹配异常；artifact 已锁定 11-06，但建议 triage 落库时持久化事件字段以长期防漂移。
- CI run44 未写入仓库 CI 表（`audit/CI_SUCCESS_2026-11-15.md` 止于 #34），本次按外部记录采信，建议补登以保持证据链自洽。

## 最终状态

**PASS**：FX/商品缺失 SPY/VIX → INSUFFICIENT_DATA 测试通过；TAIEX/KOSPI 事件合同确定；249 proof 与 CI run44 一致；无 P0/P1。V4 可签署。
