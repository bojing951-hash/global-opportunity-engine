# V2 工程闭环检查（独立、只读复核）

- 日期：2026-11-14
- 对象：`global-opportunity-engine`，分支 `architecture/research-v2`，冻结 HEAD `bad22cd`（代码提交 `85f14d2`）
- 结论：**PASS**（工程闭环四项通过；无新增 P0/P1。复核期间并行落地的 `7f289ad` 仅新增一份 audit 文档，
  代码/manifest 未变；遗留项仅为既有 P2 与已披露研究限制 V2-08，见文末）

## 1. DETECTION_CONTRACT 日期语义 — PASS

- 合同（`contracts/DETECTION_CONTRACT.md:4-11`，随 532d819 修订）：`date` 为 detection/decision date；
  macro/valuation 的 `date` 是 availability date（可行动日），`available_date` 为同一时间戳，
  `evidence.observation_date` 为原始参考期；recency/decision 禁止使用未发布的观测日。
- 代码一致：
  - `goe/features.py:546-570,650`：`point_in_time` 时宏观面板重索引到 availability
    （`macro_dates_are_availability=True`）。
  - `goe/anomalies.py:148-149`：该 meta 为真时 `availability()` 原样返回；`anomalies.py:161-172,243-265`
    输出 `date == available_date`，宏观/估值的 `evidence.observation_date = date - release lag`。
  - recency 只用 `available_date`：`goe/timesemantics.py:60-77`（`filter_recent`）、
    `goe/opportunities.py:190-195,222-226`（current / anoms_since）。
- DB 实测（`data/goe.db`，1506 条 anomaly）：14 条含 `observation_date` 的宏观 anomaly 全部满足
  `date == available_date`、`observation_date` 为更早参考期（如 `2026-05-16` / `2026-04-01`，+45d），
  `date != available_date` 为 0 条，与合同/代码一致。
- 残差（既有 P2/P3，非 live 路径）：`tests/test_time_semantics.py:44` 对非 PIT 合成特征仍断言宏观
  `date == observation`；该路径 `macro_dates_are_availability=False`，不进入 live 特征/DB。
  建议后续补一条 live/PIT 语义回归断言，不影响本次结论。

## 2. Git 与发布物 — PASS

- 核验启动时 `git status --porcelain` 为空；HEAD `bad22cd0c3d599b5b7a5e075e3e0e6246e9c184f`，
  log 为 `bad22cd`（manifest re-freeze）← `85f14d2`（P2 wording）← `5db6e33`。
- 复核期间（21:31）另一并行代理在 `bad22cd` 之上提交 `7f289ad`（仅新增
  `audit/V2_FINAL_VERIFICATION_ENGINEERING_2.md`，`git diff --stat bad22cd..HEAD` = 1 file, +92，
  无代码/配置/数据/manifest 改动）。故最终 HEAD=`7f289ad`，冻结锚点 `bad22cd` 仍完整、代码
  仍为 `85f14d2`；除此之外工作树干净。
- `audit/releases/release_85f14d2ff7.json`：`git_commit=85f14d2ff78c…`、`git_dirty=false`、
  `test_count=167`、scan `scan-20261114T125130Z-574f7b` `status=success`（as_of `2026-11-13`，
  1506 anomalies / 11 opportunities），artifact SHA256 实测与 manifest 完全匹配：
  report `329b1f77…`、scan `dc913bb9…`。
- 本报告是最终唯一未跟踪文件（非代码改动）。

## 3. 离线测试 — PASS

- manifest 记录 `test_count=167`；前序冻结（`5db6e33` / `release_532d819dcf`）亦为 167，
  与 `V2_FINAL_VERIFICATION_RESEARCH_2.md` 记载一致。
- 本次实测：`pytest tests -m "not network"` 收集 **168**（177 total，9 network deselected），
  进度中恰有 1 个 skip（默认跳过的 slow 真实数据 V2 测试），其余全部通过，**exit code 0**，
  即 **167 passed / 1 skipped**，与 manifest `test_count=167` 一致。
  （`addopts=-q` + CLI `-q` 的 `-qq` 会抑制末尾汇总行，故以 exit 0、收集数与进度中的 skip 计数为证。）
- `V2_FINAL_ACCEPTANCE.md` 中 “166 offline tests” 为旧提交遗留措辞，属文档 P2，不影响 85f14d2 的 167。

## 4. 新增 P0/P1 — 无

- P0：V2-01、V2-02 均 FIXED（V2 文件已跟踪；release gate 要求 clean/test_count/success/哈希/拒绝覆盖）。
- P1：V2-03~V2-07、V2-09 均 FIXED；V2-08 为 OPEN 的研究限制（无独立测试窗口、评估对象为
  asset cards 而非 D 的研究问题，`DISCOVERY VALUE: NOT VALIDATED`），已披露且非工程回归。
- 既有 P2/P3：`test_count` 仍由调用方自报、无测试证据哈希；非 PIT 测试语义断言（见第 1 节）；
  `V2_FINAL_ACCEPTANCE.md` 的 “166 offline tests” 旧措辞。均不阻断工程闭环。

## 遗留 P0/P1

- P0：无。
- P1：仅 V2-08（研究评估限制，已披露，`NOT VALIDATED`），不属工程闭环阻断项。
