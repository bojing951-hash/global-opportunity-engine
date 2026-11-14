# 最终独立发布 QA（FINAL RELEASE QA）

- 对象：`architecture/research-v2`，冻结 commit `168291d`（代码 `a20ce29`），manifest `audit/releases/release_a20ce293f4.json`
- 方式：独立只读复核；攻击用例仅写入 `/tmp`；另建 `/tmp/goe_qa_clone` 全新 no-data clone；未改动任何代码
- 结论：**PASS WITH ISSUES（有条件通过）**；发布门与 179 测试证据可机验；无新增 P0/P1；残留 1 个既有文档层 P1（见第 4 节）

## 1. 真实 proof / manifest —— PASS

| 检查 | 结果 |
|---|---|
| `verify_test_proof(...)` | **ACCEPT**：`passed=179 failed=0 skipped=0`，commit `a20ce293f46667785baf01d3a955e9aa4895df7e`，exit 0 |
| proof log SHA-256 | `22f0fcbb161c506e2758fd65ea0b3579dcbad328aa8067be86dadbee4024b7e3`，与 proof、manifest 完全一致 |
| rerun log SHA-256 | `066c5a241c19e69d9102f78ad762e3fc9be110c3f1920c1682fa08d1d09ecabf`，与 manifest 一致 |
| rerun 计数 | `179 passed / 0 failed / 0 skipped / 10 deselected / 0 errors`，与 manifest 记录一致；日志尾行 `179 passed, 10 deselected` |
| git 跟踪 | manifest、proof.json、proof log、rerun log 均被 `git ls-files` 跟踪；`168291d` 恰好新增这 4 个证据文件（evidence-only，175 行） |
| commit 关系 | `a20ce29` 是 HEAD `168291d` 的祖先；`a20ce29..168291d` 仅含 4 个证据文件，无 goe/tests/config 变更 |
| clean tree | 全新 clone `@168291d` 为 100% clean（`git status --porcelain` 0 行）；当前开发工作树另有 1 个文档改动 `M audit/V2_FINAL_ACCEPTANCE.md`（他人审计编辑，非代码）及未跟踪的审计报告 |

**判定：真实证据链成立，179 通过数为机器证据而非调用方声明。**

## 2. 攻击矩阵 —— PASS（7/7 全部拒绝）

| 攻击 | 实测结果 |
|---|---|
| shell command（`sh -c "printf '179 passed'"`） | **REJECT**：`proof command must be a direct full python -m pytest tests invocation` |
| 反向 rename（`goe/cli.py -> audit/test_evidence/cli.py`） | **REJECT**：`_dirty_code() == True`（rename 源路径已纳入检查） |
| 正向 rename（`audit/test_evidence/x -> goe/payload.py`） | **REJECT**：`_dirty_code() == True` |
| `-k` 子集 | **REJECT**：同“非完整 python -m pytest tests”错误 |
| 伪造计数（proof 改 `passed=9999`，日志不变） | **REJECT**：`test proof passed count disagrees with log` |
| 缺失日志 | **REJECT**：`test proof log is missing` |
| stale commit（未知 commit；或祖先 commit 但后续改过代码） | **REJECT**：`test proof commit is not an ancestor with only evidence/docs changes` |
| 真实 proof 对照 | **ACCEPT**（`passed=179`），无误杀 |

**判定：上一轮 P1（shell 伪造、双向 rename 绕过）已关闭；本轮未发现新的门禁绕过。**

## 3. 全新 no-data clone —— PASS

- `/tmp/goe_qa_clone`：`git checkout 168291d`，`git status --porcelain` 0 行，**无 `data/goe.db`、无 reports**
- `python -m pytest tests -o addopts= -q -m "not network and not realdata"`
- 结果：**179 passed, 10 deselected, 0 failed, 777 warnings in 141.10s**，exit code 0
- 与 manifest/proof 的 179 一致；**测试计数 179 可复现**

## 4. 新增 P0/P1 与残留问题

- **新增 P0：无**
- **新增 P1：无**（release gate 的 7 类攻击均被拒绝，无新绕过）
- **残留 P1（既有、非本轮新增，文档层）**：`audit/V2_FINAL_ACCEPTANCE.md` 第 5 行仍写 “Tests: 166 offline passed…”，而同一文件第 15 行写 “fresh clone 179 passed/10 deselected”，proof 实测也是 179。**tracked 文档内部自相矛盾**，与上一轮 QA 指出的“文档计数与 proof 不一致”属同一未闭合问题；且该文件当前在工作树中未提交。建议打 tag 前改为 179 并提交。
- **P2（记录）**：当前开发工作树非 clean（仅审计文档未提交），不影响用 clone 复验 179；`verify_test_proof` 不校验“当前工作树”而校验 proof 记录，故既有证据仍有效，但“frozen commit + clean tree”在开发工作树层面未完全成立。

## 5. 最终裁决

**PASS WITH ISSUES（有条件通过）**：代码/测试证据链、manifest、rerun、攻击矩阵、全新 no-data clone 179 全部通过；无新增 P0/P1。发布前唯一需处理的是既有文档层 P1：把 `audit/V2_FINAL_ACCEPTANCE.md` 的 166 更正为 179，并提交该文档及当前未提交的审计编辑（不涉及代码）。
