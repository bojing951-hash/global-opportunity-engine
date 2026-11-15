# 独立工程 QA — 广义研究发布（architecture/research-v2，验收快照 d5f48c9）

- 结论：**接受（ACCEPT）**（仅对远端 `d5f48c9` 快照；验收后本地并发提交见 §9）
- P0：**无**
- P1：**无**
- 验收对象：远端 `architecture/research-v2` @ `d5f48c9`（验收开始时本地 HEAD 同为此提交）；发布证明 `audit/releases/release_bb6c2b7b05.json`（测试提交 `bb6c2b7b05`，243 tests）
- 方式：只读；哈希/结构核验、干净临时克隆重放校验、GitHub Actions 公开页面独立读取、git refs 对比。未改任何代码。
- 时限：4 分钟时间盒；CI 在首次读取时仍为 in-progress，完成后复核为 Success。

## 1. 核验结论

| 核验项 | 结论 | 独立证据 |
|---|---|---|
| Release proof 接受 243 tests | **PASS** | 干净克隆中 `verify-release` 返回 `status: accepted`、`passed: 243`、required/executed sha256 同为 `ba7656d6685199f13c1037d75b8bd5c8591454c2cd77f4c0dee7d46783812ace` |
| 测试证据完整、无跳过/失败 | **PASS** | junit：tests=243、failures=0、errors=0、skipped=0；log：`243 passed, 10 deselected`；log/junit sha256 与 proof 记录一致 |
| Scan 证据与产物绑定 | **PASS** | scan_id `scan-20261115T044634Z-b68802`、as_of `2026-11-13`、config/data hash 与 release 一致；report/scan/pipeline sha256 与清单逐项一致 |
| GitHub Actions 最新 run @ d5f48c9 | **PASS** | run **#34**（id `43721641973`），head `d5f48c9`，workflow `verify-release`，页面 `Status Success`，总时长 `2m 21s`，job `replay-release-proof` `2m 17s` |
| main / V1 / B 未被动过 | **PASS** | 本地与远端一致：`main`=`e5da620`；`fix/autonomous-audit-remediation`（B）=`1f2b341`；`v1-frozen-1f2b341` tag→`1f2b341`；验收快照 `d5f48c9` 领先 main 129、落后 0 |
| P0 / P1 | **无** | 未发现证据完整性、CI、分支隔离或显著工程缺陷 |

## 2. 证明与测试证据

- `audit/releases/release_bb6c2b7b05.json`：`git_commit=bb6c2b7b05...`、`git_branch=architecture/research-v2`、`git_dirty=false`、`exit_code=0`、`passed=243`、`skipped=0`，proof 结构为 `goe-test-proof/v4`。
- proof 的 `required` 与 `executed` 均为 243、sha256 相同；`junit_sha256=38c0e301...`、`log_sha256=34542d93...` 与本地实测哈希一致；junit 内 243 个 testcase，无 failure/error/skip。
- 在干净临时克隆（checkout `d5f48c9`，工作树 clean）执行：
  `python -m goe.cli verify-release --proof audit/test_evidence/20261115T135504Z_bb6c2b7b05.proof.json --no-rerun`
  → `{"status":"accepted","commit":"bb6c2b7b05...","category":"offline","passed":243,...}`，rc=0。
- 证明提交 `bb6c2b7` 与 HEAD `d5f48c9` 的差异仅为 `audit/` 下 proof/release 文件；`verify-release` 的 ancestor + 允许路径规则接受该差异，CI 在 `d5f48c9` 上重放通过。

## 3. Scan 证据

- scan：`scan-20261115T044634Z-b68802`，as_of `2026-11-13`，mode `offline`，readiness_ok `true`。
- 计数：prices 358310、indicators 159508、anomalies 1506、transmissions 5、opportunities 11。
- 产物哈希与 release 清单一致：
  - `reports/report_2026-11-13.md` = `7ac3425521677f35a3c6723eddf4c7736396227f2ec0fa5d928bdc6686f62fa0`
  - `reports/scan_2026-11-13.json` = `cd0bc502005e3f560837ff1a2eedb7835364d6ad8716f652b386580fdb1ff20b`
  - `exports/pipeline_2026-11-13.json` = `9e6bd81adf1bca8f9c233ef5c22ca641a8259655caace168647c34858179e2d3`
- 报告头部 scan ID、配置哈希、数据快照哈希与 release/scan 一致。

## 4. GitHub Actions 实际运行

- 公开页面：<https://github.com/bojing951-hash/global-opportunity-engine/actions/runs/43721641973>
- run **#34**，触发于 `2026-11-15T13:56:41Z`（push `d5f48c9`），workflow `verify-release`，job `replay-release-proof`。
- 首次读取（13:56:45Z 左右）页面显示 `In progress`；稍后复核为 `Status Success`、`completed successfully`，总时长 `2m 21s`。这是实际最新 run，不是历史 run 复用。
- CI 脚本按排序选取最新 proof，并以不带 `--no-rerun` 的方式重放；该 run 绿色即表示 243 tests 在 `d5f48c9` 上重放通过。

## 5. 分支隔离

- `git ls-remote origin` 与本地 refs 一致（验收快照时点）：
  - `architecture/research-v2` = `d5f48c9`（验收开始时本地 HEAD；工作树无 tracked 改动；远端复核时仍为 `d5f48c9`）
  - `main` = `e5da620`（未被本分支推进；快照领先 129、落后 0）
  - `fix/autonomous-audit-remediation`（B）= `1f2b341`
  - tag `v1-frozen-1f2b341` → `1f2b341`（V1 未被移动）
- 结论：本发布只推进 `architecture/research-v2`，未改写 main/V1/B。
- 注：验收完成后本地出现未推送提交 `8406799`（见 §9），远端分支仍停留在 `d5f48c9`。

## 6. P0 / P1

- **P0：无。** 无阻断发布、证据不可复现或 CI 红色问题。
- **P1：无。** 未发现数据/证明哈希不符、测试被跳过、run 结论不符或分支被误改。该判断仅覆盖 `d5f48c9`；验收后未推送的本地提交 `8406799` 尚未被证明/CI 覆盖（见 §9），不并入本结论。

## 7. P2 / 非阻断观察（不影响本次接受）

1. `audit/CI_SUCCESS_2026-11-15.md` 目前只记录到 run 31，未补录本次 run #34；属文档滞后，建议下次 docs 提交补齐。
2. `reports/scan_2026-11-13.json` 的顶层 `meta` 中 `status`/`mode` 为 `null`；release 中的 `success`/`offline` 来自运行记录而非该文件，哈希绑定完整，但单看 scan 文件无法自证状态。
3. 报告注明 `降级=True`、关键宏观序列 `EA_HICP` 过期（2 条）；release 仍记 `readiness_ok=true`。该限制已在报告中披露，属数据质量已知项，不阻断本次工程验收。
4. 主工作树存在并行 QA 产生的未跟踪文件 `audit/QA_GENERALIZED_FINAL.md`，以及并行研究运行产生的 `research_results/2026-11-13/*/RF-*` 未跟踪产物；proof 生成时 `git_dirty=false`，CI 重放前会 `git clean -fdx`，不影响发布证明。本次报告写入未触碰这些文件。

## 9. 验收后并发变化（不推翻 d5f48c9 结论，但阻断对新 HEAD 的签署）

- 复核完成时本地 HEAD 已变为未推送提交 `8406799`（`fix(research): version artifact directories; remove Japan-specific labels from generic templates`，2026-11-15 21:59:52 +08，改动 `goe/research_engine.py`，15+/11-）。
- 远端 `origin/architecture/research-v2` 仍为 `d5f48c9`；`main`/`v1`/B 未移动。即：已推送并跑过 CI 的发布仍是 `d5f48c9`，`8406799` 属本地在途改动。
- 因 `8406799` 在 proof 提交 `bb6c2b7` 之后改动了 `goe/`，`verify-release` 的 `_check_commit` 会判定“代码在证明后变更”而拒绝；该提交尚无新 proof，也无对应 GitHub Actions run。
- 结论：`release_bb6c2b7b05` 的接受结论只对 `d5f48c9` 成立；若要把 `8406799` 作为新 HEAD 发布，必须重新生成 243 tests proof 并等待 CI 绿色后再签署。此项为验收后的工作树漂移，不是 `d5f48c9` 的 P0/P1。


## 8. 方法与限制

- 未在本地重跑完整 243 tests；采用 proof v4 + junit/log 哈希 + 干净克隆结构校验 + CI 实际重放四重证据。
- GitHub REST API 匿名限流（403），run 状态通过公开 Actions HTML 页面独立读取并复核。
- 本次为工程发布 QA；研究结论的有效性、广义化方法论不在本次验收范围。
