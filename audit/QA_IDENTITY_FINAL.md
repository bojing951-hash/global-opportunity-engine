# QA_IDENTITY_FINAL — 最终工程复核（身份不可变 / PIT / 发布证据）

- 复核时间：2026-11-15（Asia/Hong_Kong）
- 分支：`architecture/research-v2`
- HEAD：`1a32b1f7e7cc8448d90802fb610c1fe40d1af794`（最终代码 `9f7e54edc28865888af01c734ca0a44e4b1a5dd5`）
- 复核方式：只读 + 定向运行验证；未改动产品代码、测试、配置或证据文件，仅新增本报告。
- 结论：**不通过（HOLD，不批准工程冻结）**。发现 1 个 P1（PIT 时间校验缺口），0 个 P0。

## P0

无。

## P1

### P1-1 PIT 外部证据仍可接受未来日期（vintage / observation_date / curve date）

**问题。** `goe/evidence/external.py` 对 consensus 只过滤了 `publication_time` 与 `available_at`，对 OIS 也只过滤了这两列；`vintage`、consensus 的 `observation_date`、OIS 的 `date` 没有与决策时点 `cutoff` 比较。因此，只要 `publication_time/available_at` 在过去，未来版本、未来观测期或未来曲线日期仍会被当作“已可用”证据返回。

相关位置：

- `goe/evidence/external.py:63-78`：consensus 仅按 `publication_time/available_at` 过滤；`vintage` 未解析，`observation_date` 未校验。
- `goe/evidence/external.py:124-145`：OIS 仅按 `publication_time/available_at` 过滤；`date`、`vintage` 未与 `cutoff` 比较。

**可复现证据（2026-11-15，本地 `.venv` Python 3.12.13）：**

1. consensus：`available_at=publication_time=2026-02-10`，`vintage=2027-01-01`，`kind=actual`，`forecast_target=2026-01-01`，以 `as_of=2026-02-15` 查询，返回了 `vintage=2027-01-01` 的证据，而不是 `None`。
2. consensus：`observation_date=2026-06-01`（晚于 `as_of=2026-02-15`），其余时间在过去，仍返回证据。
3. OIS：2Y/10Y 的 `date=2026-06-01`（晚于 `as_of=2026-02-15`），`available_at=2026-02-10`，返回 `"2s10s=0.50pp"`；同一场景下 `vintage=2027-01-01` 也返回证据。

**影响。** 研究证据可在决策时点使用未来版本/未来观测值，构成前视（lookahead）。这直接违反 `PROJECT_STATE.md` 第 93 行“future publication/vintage ... rejected”的声明，也违反本任务第 2 项 PIT 要求。它不会让程序崩溃，但会污染研究结论，属于研究诚信类 P1，不是可接受残余。

**修复要求。** 对 consensus 的 `vintage`（按日期解析时）与 `observation_date`、OIS 的 `date` 与 `vintage` 增加 `<= cutoff` 校验；无法解析为日期的 vintage 应明确拒绝或按契约定义处理，不能静默放行。补充“未来 vintage / 未来 observation_date / 未来 curve date”测试后，重新生成 proof/manifest 并重跑 CI。

## P2（非冻结阻断，但应记录）

- **状态机存在显式两跳重开路径。** `set_research_status` 直接拒绝 `research_complete -> active/intelligence/handoff_pending/handoff_failed`（已通过定向测试），但允许 `research_complete -> archived`，随后 `archived -> active`。该路径会写事件，不是“静默”重开，故不按 P1 计；但它与 `PROJECT_STATE.md` 第 94 行“completed cannot be reopened”的强表述不完全一致。建议把 `archived` 也纳入终态约束，或明确限制 `archived -> active`。

## 已验证通过项

### 1. 身份不可变与状态

- `goe/research_identity.py`：`research_theme_id` 不含日期，跨日期稳定；`research_id` 含 `as_of`，事件 id 随日期变化。
- `goe/db.py:819-855`：同一 `research_id` 的 `as_of`、`instruments` 变更被拒绝；`research_theme_id` 在已有值时变更被拒绝；upsert 的 ON CONFLICT 不更新 `status`，完成状态不会被静默重置。
- `goe/db.py:886-897`：直接 `research_complete -> active` 被拒绝（`cannot be reopened`）。
- `goe/db.py:899-916`：`record_identity_alias` 保留旧 id 映射，旧 task 仍指向旧 `research_id`。
- 定向测试：`tests/test_research_identity.py` + `tests/test_external_evidence.py` 共 **10 passed**（0.90s）。
- 说明：P2 的两跳路径见上；直接重开要求本身通过。

### 2. PIT 外部证据（除 P1-1 外）

- 未来 `publication_time/available_at`：拒绝。
- forecast：未来 target 仅在 `publication_time/available_at` 均不晚于 cutoff 时接受。
- actual：未来 target 拒绝。
- 曲线：跨 currency/curve_id、provider、units、2Y/10Y 日期不一致、缺 2Y 或 10Y、超过 `max_age_days` 均拒绝；混合曲线不会拼接。
- 但 `vintage`、`observation_date`、OIS `date` 的未来值未校验，见 P1-1。

### 3. 230 测试证明与发布清单

- 证明：`audit/test_evidence/20261115T084633Z_9f7e54edc2.proof.json`
  - `passed=230`，`skipped=0`，`failed=0`，`errors=0`
  - required/executed 均为 `count=230`，SHA-256 一致
  - JUnit `tests=230 / failures=0 / errors=0 / skipped=0`
  - 证明内 `rerun`：230 passed / 230 executed / 0 skipped
- 发布清单：`audit/releases/release_9f7e54edc2.json`
  - `git_commit=9f7e54edc...`，`git_dirty=false`
  - 与 proof 的 required/executed SHA-256 一致
  - 三个 scan artifact 的 SHA-256 与清单一致
- 结构校验（不重跑）：`.venv/bin/python -m goe.cli verify-release --proof audit/test_evidence/20261115T084633Z_9f7e54edc2.proof.json --no-rerun` 返回 `"status": "accepted"`，230/230。
- 独立 scan 校验：`verify_scan_evidence(store, require_artifacts=True)` 通过，`scan-20261115T044634Z-b68802`；prices=358310、indicators=159508、anomalies=1506、transmissions=5、opportunities=11，readiness ok。
- 说明：受 6 分钟时限，本次未在本机重跑完整 230 测试；完整跨 OS 重放由 CI run 23 完成，证明内的 rerun 也为 230。

### 4. GitHub Actions run 23

- 公共 HTML：<https://github.com/bojing951-hash/global-opportunity-engine/actions/runs/43696202592>
- HTML 元数据解析：`runNumber=23`，`conclusion=WORKFLOW_RUN_CONCLUSION_SUCCESS`，commit `1a32b1f`，分支 `architecture/research-v2`，标题含 `(230 tests)`，耗时 2m12s。
- 运行页正文也显示 `Status / Success`，commit `1a32b1f`。

### 5. main / V1 / B

- `main`：`e5da620cafce5b6214252de35538c70f7112aa3a`，与 `origin/main` 一致；未被本分支改写。
- V1 tag：`v1-frozen-1f2b341` -> `d6269703f1308a65f81afff4b764c6e28d5e8972`，与远端一致。
- `fix/autonomous-audit-remediation`：`1f2b341`，保持 V1 基线。
- B（外部 investment-agent）：不在本仓库内，无法从本仓库独立证明其工作区未被写入；仓库侧只存在 fact-only handoff adapter，未发现向 B 写入产品或数据的代码路径。此点作为外部边界说明，不冒充已验证。

## 工程冻结状态

**HOLD / 不批准。** 修复 P1-1（PIT 未来日期校验）并补充回归测试后，重新生成 230+ 测试证明与 `release_9f7e54edc2` 对应的新 manifest，重跑 CI，再签最终冻结。P2 状态机路径建议同轮一并收紧。
