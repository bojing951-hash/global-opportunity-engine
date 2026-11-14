# QA V2 RELEASE CLOSURE — independent verification

- 验证对象：`9f98e1c`（proof/manifest commit，代码 `08dd069`）
- 验证方式：独立只读复核 + `/tmp/v2_verify_9f98e1c` 全新 no-data clone
- 结论：**PASS WITH ISSUES**（两个指定 P1 的原始复现均已被拒绝；但有 1 个工作树 clean 问题与 1 个 release-gate 对称绕过）
- P0：无

## 1. 指定 P1-1：shell 伪造 command

- 以真实 proof 为模板，改 `command=["sh","-c","printf '176 passed'","tests","pytest"]`：
  `verify_test_proof` 抛 `ReleaseError: proof command must be a direct python -m pytest tests invocation`。
- 真实 proof（`.../.venv/bin/python -m pytest tests ...`）被接受，`passed=178`。
- proof 计数与 log 交叉校验生效（改 9999 被 hash/count 拒绝）。
- **判定：FIXED（原始攻击面）**

## 2. 指定 P1-2：staged rename 绕过 clean-tree

- clean clone `9f98e1c` 上：`git mv audit/test_evidence/20261114T160742Z_08dd069324.log goe/payload.py`
  → `_dirty_code()` = **True**。
- **判定：FIXED（指定方向 audit→goe）**
- **新问题（release gate，P1）**：反方向未被覆盖。clean clone 上
  `git mv goe/cli.py audit/test_evidence/cli.py` → `_dirty_code()` = **False**。
  即把代码文件移入豁免目录（`audit/test_evidence/`、`audit/releases/`）仍可生成
  `git_dirty=false` 的 proof，而 worktree 已缺少该代码文件。建议同时校验 rename 的源路径，
  或改用 `git diff --name-only HEAD` + `git diff --cached --name-only` 白名单。
- P2（非新 P1）：`verify_test_proof` 接受 `python -m pytest tests -k ...` 子集命令；实测
  `-k test_smoke` + `passed=2` 被接受，且 `build_manifest` 只要求 rerun passed 与 proof 相等，
  不设期望总数下限。manifest 会如实记录较小计数，非“伪造成 178”，故定 P2。

## 3. 真实 proof / manifest

| 检查 | 结果 |
|---|---|
| `verify_test_proof(20261114T160742Z_08dd069324.proof.json)` | 接受；commit `08dd069`，178 passed / 0 failed / 0 skipped / 10 deselected |
| proof log 被 git 跟踪 | 是（`git ls-files` 含 `.log` 与 `.proof.json`） |
| proof log SHA-256 | `d5f46841...0455`，与 proof、manifest 中记录一致 |
| rerun log | `audit/test_evidence/rerun_20261114T160852Z.log` 已跟踪，尾行 `178 passed, 10 deselected`；SHA-256 `a7f6c90f...fd5a` 与 manifest `rerun.log_sha256` 一致 |
| rerun 计数 vs proof | 178 = 178（另 failed/skipped/deselected 均一致） |
| fresh clone 中 verify | 同 proof 在 `/tmp/v2_verify_9f98e1c` 仍被接受（HEAD=9f98e1c 为 08dd069 的 evidence-only 后继） |

**判定：PASS**

## 4. clean tree / fresh no-data clone

- **`git status` 非 clean**：4 个已跟踪文档未提交修改（mtime 00:09:16）：
  `TEST_RESULTS.md`、`audit/EXECUTION_STATE.md`、`audit/V2_FINAL_ACCEPTANCE.md`、`audit/V2_ISSUES.md`；
  内容为 176→178 / 补记 P1-G/H。HEAD `9f98e1c` 的 **tracked 文档仍写 176**，而 proof/manifest 为 178。
  这属于既有 P1-3 未闭合；非代码改动，但“frozen commit + clean tree”不成立。
- fresh no-data clone（`/tmp/v2_verify_9f98e1c`，无 `data/goe.db`、无 reports）：
  **178 passed, 10 deselected, 0 failed, ~65s**。
- **判定：clean-tree 要求 FAIL（文档层）/ 测试 PASS**

## 5. 剩余 P0/P1

- **P0：无**
- **P1（既有，未闭合）**：当前工作树非 clean；冻结 commit 的 tracked 文档（176）与 proof（178）不一致，需提交/回退 4 个文档改动后复验。
- **P1（新，release gate）**：rename 反方向（代码文件 → `audit/test_evidence/`）可绕过 `_dirty_code`。
- **P2**：pytest 子集参数未被 pin、manifest 无机验函数（既有）、P1-C 证据可得性占位（既有，超出 release gate 范围）。
