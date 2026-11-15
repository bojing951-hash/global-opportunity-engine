# QA_SCAN_FINAL_C — scan-evidence v3 独立红队复核（C 角度）

- 复核对象：冻结 HEAD `9384b5b`（branch `architecture/research-v2`；被审业务代码 `5bcaa5d`）
- 时间：2026-11-15；只读复核，除本文件外未改仓库代码/数据；实验全部在 `/tmp/qa_scan_c/` 的 DB/artifact 副本上进行
- 方法：真实 DB 副本逐项注入 + 合成 DB（复用 `tests/test_scan_evidence.py::make_scan`）+ clean clone `9384b5b` 的 proof 接受验证
- 结论：**PASS WITH ISSUES（定向 P1 修复全部通过；发现 1 个残留 P1：output_fingerprint 覆盖面不完整）**
- 新增 P0：**0**；新增 P1：**1（残留/更窄，见 P1-C1）**；Phase 1：定向修复可验收，全量“输出不可篡改”表述仍不能成立

## 0. 复现命令（真实 DB 基线）

```bash
.venv/bin/python -c "from goe.db import Store; from goe.scan_evidence import verify_scan_evidence; \
e=verify_scan_evidence(Store('data/goe.db')); print(e.scan_id,e.data_hash[:16])"
# -> scan-20261115T041932Z-50a761 9350b109d05e0131  (ACCEPTED)
.venv/bin/python -m pytest tests/test_scan_evidence.py -q -o addopts=
# -> 8 passed in 0.45s
```

## 1. 定向 P1 验证矩阵（真实 DB 副本，UPDATE 后回滚）

| # | 攻击/场景 | 预期 | 实际 | 判定 |
|---|---|---|---|---|
| 1 | `prices.open/high/low` +5/-5 | 拒绝 | `scan data_hash does not match recomputed DB content` | ✅ |
| 2 | `prices.volume=0` | 拒绝 | 同上 | ✅ |
| 3 | `prices.close` +1（回归） | 拒绝 | 同上 | ✅ |
| 4 | `indicators.value` +1 | 拒绝 | 同上 | ✅ |
| 5 | `anomalies.magnitude/score` = -999/999 | 拒绝 | `scan output content changed after the scan` | ✅ |
| 6 | `transmissions.confidence/status` 改 | 拒绝 | 同上 | ✅ |
| 7 | `opportunities.status='excluded'/score=999` | 拒绝 | 同上 | ✅ |
| 8 | 次日早上抓取 as_of bar：`fetched_at='2026-11-14T01:00:00Z'`（< scan start） | 接受 | ACCEPTED | ✅ |
| 9 | `prices.fetched_at='2026-11-15T04:20:00Z'`（> started 04:19:32Z） | 拒绝 | `prices rows have fetched_at after the scan started` | ✅ |
| 10 | `indicators.fetched_at` 同值（> scan start） | 拒绝 | `indicators rows have fetched_at after the scan started`（已覆盖 indicators） | ✅ |
| 11 | `reference_date=2026-12-01`（as_of 2026-11-13，差 18 天） | 拒绝 | `scan as_of ... is stale (18 days > 7)` | ✅ |
| 12 | `reference_date=2026-11-12`（as_of 在未来） | 拒绝 | `scan as_of ... is in the future` | ✅ |
| 13 | 历史合成 scan as_of=2026-01-03 + `reference_date=2026-01-03` | 接受 | ACCEPTED `scan-1`（reference_date 路径支持“同期发布”） | ✅ |
| 14 | 同一历史 scan 不传 reference_date（今天 2026-11-15） | 拒绝 | `stale (316 days > 7)` | ✅ |
| 15 | live + `stats.ingest.status='success'`，无 `ingest_runs` | 拒绝 | `live scan has no successful price ingest_run evidence` | ✅ |
| 16 | live + 仅 11-13 旧 `ingest_runs`（clean copy） | 拒绝 | 同上 | ✅ |
| 17 | live + 伪造空 `ingest_runs` success 行（finished 04:00Z） | 拒绝 | **ACCEPTED** | ⚠️ P2-C1 |
| 18 | 缺 report / 缺 scan-json / 缺 pipeline | 拒绝 | `required artifact missing` | ✅ |
| 19 | scan-json anomaly 计数 +1 | 拒绝 | `scan json anomaly count disagrees with DB` | ✅ |
| 20 | scan-json `meta.output_fingerprint` 错 | 拒绝 | `scan json meta.output_fingerprint disagrees` | ✅ |
| 21 | pipeline provenance `data_hash` 错 | 拒绝 | `pipeline export provenance hashes disagree with DB` | ✅ |
| 22 | pipeline `n_opportunities` 错 | 拒绝 | `pipeline export opportunity count disagrees with DB` | ✅ |
| 23 | pipeline opportunity id 集合错 | 拒绝 | `pipeline export opportunity ids disagree with DB` | ✅ |
| 24 | 真实 scan + 真实 report/json/pipeline | 接受 | ACCEPTED（见 §0） | ✅ |
| 25 | 报告数字 1506→999999，仅保留 4 个 provenance token | 拒绝 | **ACCEPTED** | ⚠️ P2-C2（已知） |
| 26 | pipeline `scan_id`/opportunity `status` 改（id/数量不变，重写文件） | 拒绝 | **ACCEPTED** | ⚠️ P2-C2（已知） |
| 27 | `opportunities.title/status_reason/invalidation` 改 | 拒绝 | **ACCEPTED** | ❌ **P1-C1** |
| 28 | `transmissions.title/trigger_json/conditions_json` 改 | 拒绝 | **ACCEPTED** | ❌ **P1-C1** |
| 29 | `anomalies.created_at` 改 | 拒绝 | **ACCEPTED** | P3-C1 |
| 30 | 篡改 DB 后 `build_manifest`（fake proof） | 不生成 manifest | `ReleaseError: verified scan evidence failed: scan data_hash ...`，输出目录不存在 | ✅ |
| 31 | 空 DB `build_manifest` | 不生成 | `no scan_runs evidence`，输出目录为空 | ✅ |

## 2. 新发现

### P1-C1（残留，阻断“输出内容不可篡改”的强表述）：`scan_output_fingerprint` 只覆盖部分输出列

`goe/db.py:921-939` 的指纹只选择：

- anomalies：`anomaly_id,as_of,available_date,detector,family,instrument_id,direction,magnitude,score,percentile,window,evidence_json,fingerprint`（**不含 `created_at`**）
- transmissions：`transmission_id,as_of,mechanism_id,confidence,status,evidence_for_json,evidence_against_json`（**不含 `title,trigger_json,assets_json,conditions_json,notes,created_at`**）
- opportunities：`opportunity_id,fingerprint,status,score,score_json,discovery_json,evidence_for_json,evidence_against_json`（**不含 `title,status_reason,invalidation,lifecycle_json,catalysts_json,open_questions_json,market,asset_class,instruments_json,horizon,as_of,first_seen,last_seen,archetype,updated_at,status_source,data_quality`**）

实测在真实 DB 副本上修改 opportunity 的 `title/status_reason/invalidation` 或 transmission 的 `title/trigger_json/conditions_json` 后，`verify_scan_evidence` 仍返回 **ACCEPTED**，且错误信息所声称的 “scan output content changed after the scan” 不会触发。报告/导出文件也未被要求与 DB 内容对账（P2-C2），因此人工阅读的结论字段可在 scan 后替换而不被门禁发现。
建议：对三张输出表做整行（排除纯 `created_at` 元数据或明确声明忽略列）稳定序列化哈希，至少覆盖所有进入 report/pipeline 的字段；或让 report/pipeline 与 DB 内容双向对账。修复后需新 scan + 新 proof + 新 manifest。

- 影响：定向验证的 status/score、OHLCV 已修复；但“derived outputs 已哈希”仍是部分实现，不能对外宣称“扫描输出不可事后改写”。
- 定级：P1（同 P1-1 类别、覆盖面更窄）。

### P2-C1（残留）：live ingest 只要求存在任意 success `ingest_runs` 行

`goe/scan_evidence.py:170-175` 查询 kind='prices'、status='success'、`finished_at >= date(scan.started_at,'-1 day')` 的任意一行，不校验 run 与 scan 的 `as_of`/数据覆盖/`stats_json`/错误数，也不要求 mode 非 backfill。实测插入 `prices-FORGED`（空 stats、backfill、finished 04:00Z，无对应实际抓取）后，live scan **ACCEPTED**。相比旧版“stats_json 自报 success 即通过”已明显收紧（无行则拒绝、旧 11-13 行也拒绝），但“actual successful ingest_run”仍只是行存在性，不是真实抓取证据。

### P2-C2（已知未修，重申）：report/pipeline 内容仍不与 DB 对账

report 仅校验 4 个 provenance token；pipeline 仅校验 provenance 两 hash、数量、id 集合。实测改 report 数字（1506→999999）与 pipeline `scan_id`/status 后仍 ACCEPTED。manifest 的 artifact 哈希是冻结时现算，无法证明是 scan 原产物。

### P3

- `anomalies.created_at` 未入指纹（无实质语义，但说明“整行”未覆盖）。
- `reference_date` 仅库函数参数，`build_manifest` 不暴露；生产路径无法用 reference_date 验证历史 scan（这是设计取舍，不是本次 P1）。
- `fetched_at > started_at` 在“scan 后对同一 bar 重抓/修正、值不变”时会误拒旧 scan（fetched_at 被 upsert 改写）；release 流程通常 ingest→scan→manifest，风险低，但语义上注释“only a fetch after the scan itself started is impossible”并不严格成立。
- 当前工作树被其他 agent 修改（`PROJECT_STATE.md`、`audit/RELEASE_GATE_ACCEPTANCE.md`、`audit/TEST_EVIDENCE.md` 为 M），`build_manifest(require_clean=True)` 在现工作树会拒绝；proof/manifest 只在 clean clone 可复验。这是环境状态，不是代码回归。

## 3. 真实 manifest / proof（`release_5bcaa5de06.json`）

| 检查 | 证据 | 结果 |
|---|---|---|
| scan evidence | `scan-20261115T041932Z-50a761`，358,310 prices / 159,508 indicators / 1,506 anomalies / 5 transmissions / 11 opportunities；config `7d4d8ae1…`、data `9350b109…` 与当前 DB 重算一致 | ✅ |
| artifact 哈希 | report `bd584b2a…` / scan-json `09e06dc0…` / pipeline `836b6398…`，三文件现场 sha256 全部相等 | ✅ |
| 相对路径 | manifest 全文无 `/Users`；`test_evidence.proof_path=audit/test_evidence/20261115T042208Z_5bcaa5de06.proof.json`（存在）；artifacts/scan_evidence 路径均仓库相对 | ✅ |
| 217 proof | clean clone `9384b5b` 上 `verify_test_proof(..., rerun=False)` → **PROOF ACCEPTED 217 / 0 skipped**；JUnit `tests="217" failures="0" skipped="0"`；`required_sha256==executed_sha256`；manifest rerun 217/217/0 | ✅ |
| 时序 | scan 04:19:32–04:20:02Z，proof 04:20:26–04:22:08Z，manifest 04:23:42Z；代码 `release.py:677,684,739` 顺序为 proof→scan→写盘；实测空库/篡改 DB 均无输出文件 | ✅ |
| 冻结关系 | manifest `git_commit=5bcaa5d`；HEAD `9384b5b` 与其 diff 仅 4 个 `audit/` 证据文件；proof commit 同为 `5bcaa5d` | ✅ |
| 失败不落盘 | 空 DB + fake proof、篡改 OHLCV + fake proof 均 `ReleaseError`，输出目录不存在 | ✅ |

## 4. 判定

**PASS WITH ISSUES**。A/B 列出的定向 P1（OHLCV/data_hash、输出 status/score fingerprint、stale/future、fetched_at 基准与 indicators、live ingest_runs、artifact 计数/来源、真实 217 proof、manifest 写入时序与相对路径）**全部通过独立复现**，无 P0。

剩余 P1 仅 **P1-C1**（output fingerprint 覆盖不完整，部分报告/人工可见字段可在 scan 后改写而不被发现）。若验收标准要求“所有进入报告的 derived output 字段不可事后改写”，则本项应为 **FAIL/不可冻结**；若本轮验收范围仅限 A/B 明确列出的 status/score/OHLCV，则本项为 PASS WITH ISSUES，P1-C1 应作为 Phase 1 冻结后的首个补丁（或明确降级“verified”措辞）。

**Phase 1 状态：定向修复验收通过；ENGINEERING 冻结仍需对 P1-C1 做出“修复或明确接受”的决定。** P2-C1/P2-C2 不阻断，但 release 文档不得写成“输出内容/报告内容已全量验证”。
