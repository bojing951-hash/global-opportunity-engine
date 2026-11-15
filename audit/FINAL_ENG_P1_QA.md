# 独立最终工程 QA — P1 复验

- 日期：2026-11-15（Asia/Hong_Kong）
- 冻结 HEAD：`0d5d6ac`（代码 `983854f`），分支 `architecture/research-v2`
- 方式：只读复验；干净克隆 `/tmp/goe_p1_qa`；Python 3.12.13；未修改任何产品代码
- **总判定：PASS（工程）**
- **新增 P0：0；新增 P1：0**
- **Phase 1 工程状态：ACCEPTED（工程收口）**；DISCOVERY VALUE 仍为 NOT VALIDATED

## 1. P1-01 — 干净克隆可安装、工作树不脏、CI 证据选择与 Actions 状态

| 检查 | 结果 | 证据 |
|---|---|---|
| clean clone `pip install -e .` | PASS | clone `0d5d6ac`，Python 3.12，editable wheel 构建并安装成功（含 pandas/numpy/yfinance/akshare 等依赖），退出码 0 |
| 安装后 `git status` | PASS | `git status --porcelain` 为空；`git check-ignore -v global_opportunity_engine.egg-info` → `.gitignore:43:*.egg-info`，构建产物被忽略，不污染工作树 |
| CI 清理 ignored artifacts | PASS | `.github/workflows/verify-release.yml`：`git clean -fdx` 后再执行回放 |
| CI 按时间戳选 proof | PASS | `PROOF="$(ls -1 audit/test_evidence/*.proof.json \| sort \| tail -1)"`；文件名为 UTC `YYYYMMDDTHHMMSSZ_<sha>`，字典序即时间序，非 checkout mtime |
| GitHub Actions run 19 | **SUCCESS** | run `#19` / id `43685550326`，commit `b888303`，226 tests，2m14s；公开 HTML 内嵌状态 `WORKFLOW_RUN_CONCLUSION_SUCCESS` |
| GitHub Actions run 20 | **SUCCESS** | run `#20` / id `43686642240`，commit `0d5d6ac`，227 tests，1m34s；公开 HTML 状态 `Success`，内嵌 `WORKFLOW_RUN_CONCLUSION_SUCCESS` |

结论：P1-01 已闭环；run 19/20 均为绿色，无“19 绿 20 红”问题。

## 2. P1-02 — Research ID 稳定身份

- 实现：`goe/research_identity.py`，`RC-<yyyymmdd>-<instrument>-<phenomenon-hash>`；hash 输入为 `as_of|instrument_id|detector|direction|window`，**不包含列表位置**。
- 定向测试：`pytest tests/test_research_identity.py -o addopts= -q` → **3 passed**，覆盖：
  - 重复运行同输入 → 同 ID；
  - 同一资产/不同异常 → 不同 ID；
  - 不同资产/同一异常 → 不同 ID；
  - 列表顺序无关（独立复算正序/逆序映射一致，3 个 ID 唯一）；
  - `research_v2_identity_map` 旧→新别名；
  - 旧任务仍保留旧 ID；
  - 重复 upsert 保留同一任务且仅 1 行；
  - `research_integrity()["orphan_tasks"] == 0`。
- 独立复算：`order-independent: True, unique: True`。

## 3. P1-03 — 曲线契约

- 实现：`goe/evidence/external.py` 要求 `curve_id,currency,region,curve_type,tenor,date,value,available_at,source`；同一曲线/币种/区域/类型，2Y 与 10Y 必须同日、同可用时间；`available_at <= as_of` 且年龄不超过 `max_age_days`。
- 定向测试：`pytest tests/test_external_evidence.py -o addopts= -q` → **4 passed**，覆盖：
  - 跨币种（US 2Y + EU 10Y）→ 拒绝；
  - 混合曲线（同币种、不同 `curve_id`）→ 独立复算 `None`；
  - 错误类型（`policy_path_proxy` 冒充 `ois`）→ 拒绝；
  - 2Y/10Y 日期不同 → 拒绝；
  - 缺少 10Y → 拒绝；
  - 过期（超过 `max_age_days`）→ 拒绝；
  - 单曲线完整数据 → 接受（2s10s 差值正确）。
- 未来数据独立复算：`available_at=2026-01-10`、`as_of=2026-01-05` → `None`；`as_of=2026-01-12` → 接受。

## 4. 227 证据、scan evidence、release manifest

| 检查 | 结果 |
|---|---|
| `verify-release --proof 20261115T064031Z_983854f9a3.proof.json`（主工作区） | **accepted**；227/227；required=executed `431b43078ecdf8a90e2c931a6c4d498f0a49f8dbaa98c71850ccf2e5bfdfd1de` |
| 干净克隆重放同一 proof | **accepted**；227/227；跨环境（clone + 新 venv）通过 |
| JUnit | `tests="227"`；日志 `227 passed, 10 deselected` |
| scan evidence 独立复验 | `verify_scan_evidence(store, require_artifacts=True)` 通过：`scan-20261115T044634Z-b68802`，as_of `2026-11-13`，offline，358,310 prices / 159,508 indicators / 1,506 anomalies / 5 transmissions / 11 opportunities，readiness_ok=true |
| 产物 hash | report `7ac3425521677f35a3c6723eddf4c7736396227f2ec0fa5d928bdc6686f62fa0`；scan json `cd0bc502005e3f560837ff1a2eedb7835364d6ad8716f652b386580fdb1ff20b`；pipeline `9e6bd81adf1bca8f9c233ef5c22ca641a8259655caace168647c34858179e2d3`，与 manifest 一致 |
| manifest | `audit/releases/release_983854f9a3.json` 存在；`git_commit=983854f9a3…`，`passed=227`，scan_id 与 scan evidence 一致 |

说明：干净克隆可重放 **测试 proof**；`reports/`、`exports/`、`data/` 为 gitignored，干净克隆不能重新生成 scan evidence——这是既有已接受 residual，不是本次回归。

## 5. main / V1 / B 与新增缺陷

- `main`：`origin/main` 为 `e5da620`，是 HEAD 的祖先，`HEAD..origin/main = 0`（main 未被本次工作触碰）。
- V1：tag `v1-frozen-1f2b341` 解引用为 `1f2b341`；与分支 `fix/autonomous-audit-remediation`（B）tip 相同，且 B 是 HEAD 祖先。
- 未发现新增 P0/P1。
- 工作区状态说明：主工作区当前只有两个未跟踪审计产物——本文件 `audit/FINAL_ENG_P1_QA.md` 与并行 research QA 的 `audit/FINAL_RESEARCH_P1_QA.md`；`git diff` 为空，未修改产品代码、测试或配置。

## P2 / 残余风险（不阻塞验收）

1. **scan evidence 不可移植**：CI 只回放测试 proof，scan gate 依赖本地 101MB DB 与 gitignored 产物；干净克隆无法独立重算。与 PROJECT_STATE 已列 residual 一致。
2. **CI 清理范围**：`git clean -fdx` 会删除所有 ignored 文件（`.venv/`、`data/`、`reports/`、`.env` 等），在 ephemeral runner 安全，但本地直接执行会破坏工作数据；workflow 注释“只删 build 输出”不准确。
3. **`verify-release` 语义**：命令验证测试 proof（及 commit 许可），不校验 scan artifacts；scan evidence 需 `verify_scan_evidence` 单独验证。

## 判定

- P0：**0**
- 新增 P1：**0**
- P1-01 / P1-02 / P1-03：**全部复验通过**
- 227 proof：**accepted**
- release manifest：**存在且与 proof/scan 一致**
- Phase 1 工程：**ACCEPTED**（工程可收口）
- Phase 2 / 研究发现：**PARTIAL；DISCOVERY VALUE NOT VALIDATED**（不属于本次工程 P1）
