# PIT / 状态机 / 身份 终审 QA（HEAD 2488955，code 360b161）

**结论：PASS（通过）。新增 P0 = 0，新增 P1 = 0。** P2 残留 3 条，均不阻塞发布。

- 审计对象：HEAD `2488955db57c518177bdb871f69012638c9bd480`（code `360b1614d136cecc5058dc7ec4e3aeceaa5d1c5c`），分支 `architecture/research-v2`。
- 工作区：已跟踪文件干净（`git diff` 为空）；仅新增本 QA 文件。未改动任何代码/测试/配置。
- 方法：读代码 + 定点复跑 + 独立探针 + 产物哈希核对 + GitHub Actions 公共页面核对。因 4 分钟时限，本机只复跑 16 个定点测试；完整 231 项以 proof 与 CI run 24 的跨 OS 重放为准。

---

## 1. PIT：未来 vintage / observation_date / curve date / publication / available 全部拒绝

代码证据：
- `goe/evidence/external.py:66-73`（consensus）：`available_at / publication_time / vintage <= as_of`，`vintage <= available_at`，`publication_time <= available_at`，`observation_date <= as_of`；`kind` 仅允许 actual/forecast；actual 的 `forecast_target` 不得晚于 as_of，forecast 允许未来目标（符合 PIT 语义）。
- `goe/evidence/external.py:127-133`（OIS）：`date / available_at / publication_time / vintage <= as_of`，`publication_time / vintage <= available_at`；再按 currency/region/curve_type 过滤，provider/units/curve_id 必须唯一。
- `goe/evidence/external.py:156-158`：2Y 与 10Y 必须同日、同 available_at，配合 curve/currency/region/type 的唯一性检查，曲线不会被拼接。

测试证据（已通过）：
- `tests/test_external_evidence.py::test_future_vintage_observation_and_curve_date_rejected`
- `tests/test_external_evidence.py::test_curve_rejects_dates_tenor_provider_units_type_and_staleness`
- `tests/test_external_evidence.py::test_consensus_actual_and_forecast_are_pit`
- `tests/test_external_evidence.py::test_same_curve_slope_and_cross_currency_rejected`

独立探针（使用真实函数，临时 CSV）：

| 场景 | 结果 |
|---|---|
| consensus：observation/publication/available/vintage 均为 as_of 当天（valid same-day） | 接受 |
| consensus：publication 未来、available 过去 | 拒绝（`None`） |
| consensus：vintage / observation_date 未来 | 拒绝（测试覆盖） |
| OIS：date/publication/available/vintage 均为 as_of 当天 | 接受，curve.date = 2026-02-15 |
| OIS：curve date 未来 | 拒绝 |
| OIS：vintage 未来 | 拒绝 |
| OIS：available_at 未来 | 拒绝 |
| 跨币种 / 混合曲线 / 混合 provider / 混合 units / 不同日期 / 缺 10Y | 拒绝（测试覆盖） |

定点复跑：`tests/test_external_evidence.py tests/test_research_identity.py tests/test_status_lifecycle.py`，**16 passed in 1.71s**。

**P2-1（不阻塞）**：OIS 的“陈旧”只按 `available_at` 计算（`max_age_days`），不按 `date`。探针中 `date=2020-01-01`、`available_at=2026-02-14`、as_of=2026-02-15 仍被接受。该行为不违反“未来数据拒绝”的 PIT 约束（available_at 声明为 2026 年可得，属重述/回填语义），但旧 curve date 可被当作当前曲线证据使用；建议后续对 `date` 增加最大年龄或显式 restatement 标记。

## 2. 状态机：completed / archived 不可回退到活跃流程

代码证据：
- `goe/db.py:884-898` `set_research_status`：当前为 `research_complete` 或 `archived` 时，目标为 `active / intelligence / handoff_pending / handoff_failed` 一律抛 `ValueError("completed/archived research cannot be reopened...")`。
- `goe/db.py:813-846` `upsert_research_candidate`：ON CONFLICT 更新列不含 `status`，重扫只更新内容、不重置状态；as_of/instruments/theme 变化抛不可变身份冲突。

独立探针：
- archived → active / intelligence / handoff_pending：全部拒绝。
- archived 后再次 upsert（默认 status=active）：库内仍为 archived。
- completed → active：拒绝（`test_completed_status_is_not_silently_reopened`）。
- 同一 id 改 theme：拒绝（immutable research theme conflict）。

**P2-2（不阻塞）**：`archived -> research_complete` 目前允许（探针确认，状态由 archived 变为 research_complete）。这是“终态→终态”的语义修正，不能回到活跃流程，故不构成 reopen；但建议显式定义终态间迁移表并补测试，避免把 archived 当作可改写的中间态。

## 3. 不可变身份

- `goe/research_identity.py`：`research_id` 由 as_of + instrument + phenomenon signature 内容哈希派生；`research_theme_id` 不含 as_of，是跨日期的长期主题；顺序不进入函数，重排/重扫不改 id。
- 测试：`test_identity_is_order_independent_and_content_specific`、`test_theme_is_stable_across_dates_event_is_not`、`test_immutable_identity_rejects_asset_and_date_retarget`、`test_legacy_alias_preserves_old_task_link` 全部通过。
- DB 层拒绝同一 id 改 as_of/instruments/theme；legacy alias 只新增映射，不重指旧 task（测试断言旧 task 仍指向旧 id，orphan_tasks=0）。

**P2-3（不阻塞）**：proof 的 `rerun.log_sha256=2b209eb2...` 在 `audit/test_evidence/` 下没有对应 rerun 日志文件；首次运行日志与 JUnit 齐全，且 CI run 24 已独立重放 231 项，故不构成证据缺口，但 rerun 证据不可从仓库单独复核。

## 4. 231 证明 / manifest / 扫描证据 / CI run 24

Proof：`audit/test_evidence/20261115T090019Z_360b1614d1.proof.json`
- schema `goe-test-proof/v4`；commit `360b1614d1...`；exit_code 0；**passed=231, failed=0, errors=0, skipped=0**；required/executed 均为 231；git_dirty=false。
- JUnit `tests="231" failures="0" errors="0" skipped="0"`，sha256 `c4248c66439625d0af9a04747b22201b4e488f665906849cad3a493dddc5b3a9`（与 proof 记录一致）。
- 日志 sha256 `ae49b7cf2e6e1ddec61eb3fc13984a32b56f57e68e817e21f95b8a0629606f6c`（与 proof 记录一致）。

Manifest：`audit/releases/release_360b1614d1.json`（HEAD 2488955 中提交）
- commit `360b1614d1...`，notes “PIT hotfix; 231 tests”，test_evidence.passed=231，proof_path 指向上述文件。
- scan_id `scan-20261115T044634Z-b68802`、as_of 2026-11-13；DB 中该 scan_runs 行为 `status=success, mode=offline, started_at=2026-11-15T04:46:34Z`。
- config_hash `7d4d8ae1...`、data_hash `9350b109...` 与当前 DB 重算一致。
- 扫描产物 SHA-256 全部核对通过：report `7ac34255...`、scan_json `cd0bc502...`、pipeline `9e6bd81a...`；counts anomalies=1506 / transmissions=5 / opportunities=11 与 scan JSON 一致。
- 文件 sha256：`8e45330cd39f349d70982b39ee03e02664d85452f7b66c662fcff1686e951746`。

CI run 24（公共 HTML 已核对）：
- GitHub Actions `verify-release` **#24**，run id `43697258390`，commit **2488955**，branch architecture/research-v2，conclusion **SUCCESS**，耗时 1m19s。
- https://github.com/bojing951-hash/global-opportunity-engine/actions/runs/43697258390
- 工作流逻辑：在 HEAD 检出最新 proof 并 `goe verify-release` 重放；proof commit 之后仅允许 `audit/`、`docs/`、`.github/` 及根文档变更，代码/配置/测试变更会被拒绝（`goe/release.py:509-533`）。因此 run 24 在 2488955 上 SUCCESS 等于：360b161 的 231 项证明在 Ubuntu 上通过，且 2488955 仅新增证据/文档。

## 5. 新 P0 / P1 判定

- 新增 **P0：无**。
- 新增 **P1：无**。
- 上述 P2-1/2/3 均为边界语义或证据归档完整性建议，不改变 PIT、状态回退、身份不可变与 231 证明/CI 的验收结论。

**终审：PASS。**
