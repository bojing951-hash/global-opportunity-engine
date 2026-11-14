# V2 架构 / 契约独立复核

- 复核对象：`global-opportunity-engine`，分支 `architecture/research-v2`，HEAD `1f2b341`
- 复核时间：2026-11-14 19:56 HKT（快照；复核期间另有 agent 在生成 evaluation 产物）
- 权限：只读；除本文件外未修改代码、配置、测试或 git
- 方法：静态阅读 contracts、实现、测试、release/handoff；跑目标离线测试；对真实 DB 跑一次 V2 triage 检查候选；抽查 handoff 解析与校验器；不跑全量回归、不重跑网络测试

## 结论（verdict）

**FAIL — V2 当前不具备 freeze / QA handoff 条件；research 结论为 `DISCOVERY VALUE: NOT VALIDATED`。**

V1 本身仍被保留（tag、config、DB 快照均未变），但 V2 的全部实现/契约/测试/evaluation 都还是**未提交工作区文件**，分支没有任何 V2 commit。执行架构、数据架构、研究契约三项均 FAIL。

## P0（阻断，必须先解决）

1. **V2 分支没有 V2 commit，所有 V2 资产未受版本控制。**
   - `architecture/research-v2` HEAD = `1f2b341` = tag `v1-frozen-1f2b341`；V2 相对 tag 的 tracked diff 只有 `goe/cli.py` 的 `triage` 命令。
   - `contracts/`、`goe/contracts.py`、`goe/research_triage.py`、`goe/release.py`、`goe/integration/research_handoff.py`、`tests/test_contracts.py`、`tests/test_research_v2.py`、`evaluation/`、`docs/AGENT_OPERATING_MODEL.md`、`audit/V1_FREEZE.md`、`audit/RESEARCH_V2_RESULTS.md` 全部为 `??` 未跟踪文件。
   - 结果：QA 无法 `git checkout` 到 V2；冻结清单只能记录 V1 commit；所谓 “V2 branch” 在 git 语义上仍是 V1。这是 freeze/QA handoff 的根阻断。

2. **`goe/release.py` 不是可用的 freeze gate，能在脏工作区生成“release”。**
   - 只记录 `git rev-parse HEAD`、`git_dirty: bool`，不计算 code hash，不校验 dirty，不拒绝；实测 manifest 在 V2 未跟踪、cli.py 已修改时仍可生成，内容为 `git_commit: 1f2b341...`、`git_dirty: true`，并 pin 的是 V1 的 scan（`scan-20261114T092442Z-5ef9b9`）。
   - `test_count` 由调用方传入（本次实测传 8 即记录 8），没有测试日志/命令/hash/artifact 证据；无 code hash、无 artifacts 列表、无 feature/detector version、无 QA 记录；scan 取 `scan_runs` 最新一条，不校验 `status=success`，也不校验其 config/data hash 与当前工作区一致。
   - 输出文件名 `release_<commit10>.json`，同一 commit 重跑会覆盖前一份冻结证据。`audit/releases/` 目录不存在，即当前没有任何 V2 release manifest。
   - 对照 `contracts/ACCEPTANCE_CONTRACT.md:5` 要求 “code hash, config_hash, data_hash, scan_id, test count and artifacts”，当前实现缺 code hash 与 artifacts，test evidence 也不可核验。

## P1（高，直接影响契约/研究结论）

### 数据/时间语义

3. **宏观 anomaly 的 `date` 在真实链路里是 availability date，不是 observation date；observation date 被丢失。**
   - `goe/features.py:546-570` 把宏观面板重索引到 availability（`macro_dates_are_availability=True`，`goe/features.py:650`）；`goe/anomalies.py:243-263` 直接用 feature date 作为 anomaly `date`，而 `ctx.availability()` 在 meta 为 true 时原样返回（`goe/anomalies.py:148-149`），因此 `date == available_date == obs + lag`。
   - 实测 DB：`US_CPI` 观测 `2026-04-01`，`macro_shift` anomaly 的 `as_of`/`available_date` 都是 `2026-05-16`；`evidence_json` 中没有 `observation_date`。`DetectorContext.observation_date()`（`goe/anomalies.py:161`）是死代码，从未被调用。
   - 这与 `contracts/DATA_CONTRACT.md:6`（`date` = observation_time）和 `contracts/DETECTION_CONTRACT.md:7-9`（macro evidence 必须有 `observation_date`）冲突。`tests/test_time_semantics.py` 用 observation-dated 的合成 FeatureSet 断言 `date==observation`，与生产 FeatureBuilder 的 availability-dated 语义不同，因此测试没抓住该问题。

4. **发布滞后不是“configured”，且 readiness 与 feature 各维护一份硬编码。**
   - `RELEASE_LAG_DAYS` 在 `goe/features.py:36` 硬编码；`config/macro.yaml` 无 release lag 字段；`goe/readiness.py:201` 又维护一份 `lag_by_freq`。CONTRACT 写的是 “configured release lag”（`DATA_CONTRACT.md:8`），实际不可配置且有两处真源。
   - readiness 对 CFTC 使用原始 report date（`goe/readiness.py:329-338`），没有 +4d availability；`last_positioning_date` 也暴露原始 report date。feature 层则加了 4d（`goe/features.py:587`）。

5. **关键曲线“2Y+10Y mandatory”的 staleness 未真正按期限校验。**
   - `goe/readiness.py:319-322` 只用 `SELECT 1 ... LIMIT 1` 检查关键期限是否存在，不检查新鲜度；曲线系统性检查在 `fresh_n==0` 时才 critical。若 2Y 新鲜、10Y 过期，可整体通过。与 `DATA_CONTRACT.md:23-25` “per-curve-system staleness are critical” 不一致。

### 研究契约（RESEARCH_CONTRACT / SCORING_CONTRACT）

6. **候选 schema 缺 contract 必填字段，validator 也放行。**
   - `RESEARCH_CONTRACT.md:8` 要求每个 hypothesis 有 `evidence_for`、`evidence_against`；dataclass（`goe/research_triage.py:35`）和 `validate_research_candidate()`（`goe/contracts.py:70-77`）都只检查 `id/label/type/status/implications`。
   - `RESEARCH_CONTRACT.md:16` 要求 A/B/C/D evaluation IDs；candidate dataclass / validator 均无。
   - 实测：重复 H1、空 `source`、`available_at=2099-01-01`（未来）、`hours=-1`、空 decision 文本的候选可通过 validator；validator 不校验 `available_at <= as_of`、source 非空、hypothesis 唯一/真正竞争、falsification 可执行性。

7. **优先规则与实现不一致，且有“伪 lexicographic”。**
   - `goe/research_triage.py:219-220` 构造了 `priority_key` 但**从未使用**；实际排序（`:247-250`）是 `tier, -materiality, -gap, hours, research_id`，缺 contract 的 `distinguishability` 与 `decision impact`，且 tier 桶先于 materiality。
   - gate 阈值是未经验证的任意值：`mat<0.55`、`mat>=0.65`、`gap>=0.2/0.1`、H4 的 `|1m|>=3%`（`:167`）、materiality 的 `0.5/0.3/0.2` 权重（`:82-89`）、cost `4+2*n+2` / cap 20（`:201-203`）。这正是 contract “no arbitrary weights before validation”（`RESEARCH_CONTRACT.md:18`）要禁止的。
   - `mat<0.55` 在 `:146` 直接 `continue` 丢弃，而不是记录为 intelligence；同一 theme/entity 的重复项也在 `:140-141` 静默丢弃，无 dropped-candidate dossier。合同要求候选不因 B 拒绝而丢失，但 A 侧本身已有静默丢失。

8. **“competing hypotheses”是固定模板，H3 存在恒真 bug。**
   - `goe/research_triage.py:163` 写 `gap.components.get("positioning", None) is not None`；components 字典总是包含 positioning 键，因此 H3 永远 `open`，即使 positioning 的 value 为 None。
   - H2/H5 永远 `open`（`:159-161`, `:169-171`），H1 只由 gap/mech 冲突决定；5 个假设对每个候选都一样，仅 `untestable` 偶尔变化。2026-11-13 实测 10 个候选全部 H3=open，H2/H5=open。
   - 四个 falsification 条件对所有候选完全一致（`:195-200`）；`CREDIT_RISK`/`CFTC` 对没有映射的资产不适用，也未绑定到具体 hypothesis，不满足 “observable test/threshold/data” 的实质要求。

9. **V1 对比元数据在真实链路里根本没有生成。**
   - `goe/research_triage.py:273-278` 写 `for row in store.opportunities(limit=100): v1_rows.append(dict(row))`；DataFrame 迭代得到列名，`dict("...")` 抛异常并被 `except: pass` 吞掉，`v1_rows` 永远为空。
   - 实测 10 个候选 `v1_score`/`v1_status` 全部为 null。直接 V1 影响 tier 目前不存在（这一点是 PASS），但“V1 score may be attached for comparison”的契约没有实现，且 `store.opportunities` 没有按 `as_of` 过滤（历史 triage 会挂错日期）。
   - V2 的核心 gate 变量 `residual_divergence` 来自 `compute_expectation_gap`（V1 `expectation_gap` 的同一组件），因此“独立”只是总 V1 score 不参与排序，不是独立证据来源。

### A→B handoff

10. **V2 handoff 没有 CLI/端到端入口，唯一调用方是测试。**
    - `goe/integration/research_handoff.py` 的 `handoff_v2()` 未被 `goe/cli.py` 或 pipeline 调用；`cmd_triage` 只写候选 JSON。HANDOFF contract 要求的 fake-CLI 全状态矩阵、真实 refusal 记录均不存在（只有 V1 的真实 run 记录）。

11. **L2-only artifact 可被判定 ok_valid。**
    - `parse_research_artifact()` 只在 `n_l1_rows==0 and n_l2_views==0` 时判 insufficient；实测 L1 rows=0、L2 views=17、evidence_index 非空、S8 answered 时返回 `ok_valid`。这与 `HANDOFF_CONTRACT.md:20-21` 的 “no path where L2-only artifact is completed” 冲突；现有测试 `test_l2_only_artifact_cannot_be_ok_valid` 把 evidence_index 置空，因此测不到该路径。

12. **timeout/unknown 的持久化语义丢失。**
    - `persist_v2_result()` 取 `sem = res.get("semantic_status") or "unknown"`（`research_handoff.py:67`）；adapter 的 timeout 结果没有 semantic_status，实测写入 `not_completed:unknown`，而不是 contract 要求的 `not_completed:timeout`/具体 semantic（`HANDOFF_CONTRACT.md:14-15`）。任务 ID 变成 `RC-RC-...` 双前缀；事件写到不存在的 opportunity id（SQLite 无 FK，不报错但污染事件表）。
    - `_clean()` 把 `仓位` 替换为 `净头寸`、`做多/做空/买入/卖出` 替换为 `研究判断`（`research_handoff.py:19-23`），会把事实方向改掉；banned-list 也不完整。候选 payload 在拒绝时确实保留（这一点 PASS），但“fact-only”没有语义保持测试。

### 测试与 evaluation

13. **关键测试是 tautology / 只测字段。**
    - `test_v2_evaluation_decision_rule_is_not_automatic` 断言 `discovery_value in ("VALIDATED","NOT VALIDATED")`，恒真；我用测试自带 fixture 实跑得到 `VALIDATED`（D mean 1.4167 vs 1.25，P@3 0.6667 vs 0），而测试注释写的是 “must not be VALIDATED”。这个测试既没有测 decision rule，也没有测非自动性。
    - `test_research_candidate_contract` 用 `materiality: "high"` 的合成 dict，缺 `evidence_for/against`、A/B/C/D ID 仍通过；它只测“删到 1 个 hypothesis 会 raise”。
    - `test_anomaly_contract_on_real_scan` 从 DB 读行后自己填充 `entity_kind="instrument"`、`measure=""`、`magnitude=0`、`score=0.5`，没有验证真实 anomaly 的 entity_kind、score、证据字段/observation_date；名不副实。
    - `test_research_v2_real_scan_contract` 只做字段存在性和 `validate_research_candidate`，不验证 provenance（`available_at<=as_of`）、hypothesis 竞争性、falsification 实质、lexicographic 顺序、V1 不参与；还依赖 10 分钟真实 FeatureBuilder，DB 不存在时 `skip`，CI 可通过“跳过”过 gate。
    - `test_v2_refused_result_is_not_completed` 传入 `status=not_ok, semantic_status=ok_valid`（并非 refusal），只断言 `!= completed`；不检查 `not_completed:<semantic>` 前缀、候选保留、事件类型或 exit 2。
    - `test_feature_contract_columns` 只用合成 FeatureSet；真实 `build()` 会额外加 `method_version`（`goe/features.py:635`），但 validator 不拒绝多余列，测试也看不到。

14. **V2 evaluation 是 NOT VALIDATED，且 test split 只有 n=1。**
    - 目前 `evaluation/` 有 input/mapping/ratings/results（未跟踪；结果文件 mtime 19:36），`audit/RESEARCH_V2_RESULTS.md` 也已出现（未跟踪）；结果明确 `DISCOVERY VALUE: NOT VALIDATED`，test split D n=1，决策规则要求 n>=3。这是**诚实的失败**，但意味着 research acceptance 未通过。
    - `score_ratings()` 的 `precision_at_3` 实际是 “mean>=1.5 的占比”（`goe/research_evaluation.py:163`），不是 precision@3；decision rule 只比较 mean/P@3，不检查 contract 要求的 evidence sufficiency/falsifiability “no material regression”；结果文件还打印 “D beats B and C [True, True]”，在 n=1 vs n=3 下容易误读。
    - evaluation 的 D 实测 n=10（test n=1），其余方法 12；D 的 test 无法验证。当前 rating 是单一 LLM rater，无人工标签；作为 `NOT VALIDATED` 证据可以，作为 acceptance 不行。

## P2（压缩列表）

- `DATA_CONTRACT` rule 6 要求 feature/detector versions；scan 只记 feature_version，无 detector version。
- `DATA_CONTRACT` rule 4 的 `price_data_issues` 无 DB 表/写入，仅存在于 scan meta/report（`goe/features.py:651`、`goe/reports.py:295`）。
- `Features.long` 真实列含 `method_version`，与 `FEATURE_CONTRACT` “exactly” 冲突；`validate_feature_frame` 不检查多余列。
- `FeatureBuilder._load_prices` 的 `min(self.min_history, 120)` 让 `min_history_days=504` 失效；早期历史/成员筛选可能破坏 `build(t) == build(T).slice_as_of(t)`，现有测试只检查同一 instrument 的数值。
- readiness 的关键宏观 stale 阈值 `lag+90` 与一般 stale `lag+60` 不一致；`last_positioning_date` 用原始 COT report date。
- release 文件名按 commit 覆盖、`test_count` 可由调用方伪造、scan 不校验 success/当前 config。
- `main` 不包含 V1 tag（merge-base 落后）；V1_FREEZE.md、V2 结果文件均未跟踪；V1 记录只存在于工作区。
- 候选 `evidence.source` 是 “engine/anomalies”“prices”“data_gap” 等自由字符串，不是 source_id/tier/url；`data_quality.score = gap.confidence` 实际是可用权重占比，不是数据质量。
- `required_data` 对所有候选固定 `OPEN_DATA+MISSING_DATA`；`decision_impact` 对所有候选固定；`observed_phenomenon` 在 ret/drawdown 为 NaN 时会写 “nan”（本次 10 个真实候选未触发，但代码路径存在）。
- V2 候选输出（`goe/cli.py:307-309`）无 `scan_id`/`config_hash`/`data_hash`/`feature_version`，且 triage 不写 `scan_runs`；候选无法 pin 到数据快照。

## 七份契约的完整性/可执行性

| 契约 | 完整性/一致性 | 可执行性 |
|---|---|---|
| ACCEPTANCE | 原则完整；但 “code hash/artifacts/两次 QA” 没有实现/记录 | FAIL：release.py 不满足，无 release 目录 |
| DATA | 宏观 `date` 语义与 FEATURE/DETECTION 冲突；lag 未配置；detector version 缺失 | FAIL：真实 macro anomaly 缺 observation_date；curve staleness 有洞 |
| DETECTION | 输出字段、evidence、abort 规则基本完整 | PARTIAL：validator 缺 asset_class/region/percentile、macro observation_date；测试造数据 |
| FEATURE | “exactly” 与 method_version 冲突；feature_data_quality 未落地 | PARTIAL：PIT 全等属性未测，成员筛选有 look-ahead 风险 |
| HANDOFF | contract 的状态语义清楚 | FAIL：V2 未接线；L2-only 可 ok_valid；timeout 变 unknown |
| RESEARCH | 字段要求清楚但 schema/validator 缺 evidence_for/against、A/B/C/D | FAIL：priority 规则未实现，falsification 模板化，evaluation NOT VALIDATED |
| SCORING | V1 冻结部分完整；V2 lexicographic 描述完整 | FAIL：实现用 tier 桶+不同排序键；materiality 内部是加权和；阈值任意 |

## 明确 PASS/FAIL

- **Execution architecture: FAIL** — P0 无 V2 commit、无 freeze manifest；P1 release 不能 pin code/test/artifacts，V2 handoff 未接线。
- **Data architecture: FAIL** — P1 macro anomaly 的 observation/availability 语义错误、observation_date 缺失；P1 关键曲线 staleness 不按 tenor；P2 config/lag/version/price issue 多处不一致。
- **Research contract: FAIL（`DISCOVERY VALUE: NOT VALIDATED`）** — P1 schema 缺字段/validator 过弱、priority 规则未实现、H3 恒真、falsification 模板化、V1 对比未生成；evaluation test n=1，未通过 acceptance。
- **V1 preservation: PASS（有保留条件）** — tag `v1-frozen-1f2b341` 指向 `1f2b341`，`config/` 相对 tag 无改动，V1 code/scoring 未被覆盖；DB 的 V1 scan `scan-20261114T092442Z-5ef9b9` 的 `config_hash=7d4d8a…`、`data_hash=9ddd93…` 与 `audit/V1_FREEZE.md` 一致，1506 anomalies/11 opportunities 也一致。但 V1 freeze 文档未提交、`main` 不包含该 tag，V1 的“冻结记录”不在版本控制内。

## 复现实证

- `pytest tests/test_contracts.py tests/test_research_v2.py -q -m "not network"` → **8 passed**
- `pytest tests/test_time_semantics.py tests/test_features.py tests/test_readiness_handoff.py -q -m "not network"` → **42 passed**
- `pytest tests --collect-only -q -m "not network"` → **165** offline tests；全量 **174**（9 network），与 V1_FREEZE 的 157 + V2 新增 8 相符。
- 真实 V2 triage（as_of 2026-11-13）：**10 candidates**，8 researchable（1 A / 7 B），全部 `v1_score=null`，全部 H3=open；候选示例：`RC-20261113-08 JP_EQ_N225 tier=A gap=0.709`。
- V2 evaluation：`evaluation/V2_EVALUATION_RESULTS.md` 与 `audit/RESEARCH_V2_RESULTS.md` 明确 **NOT VALIDATED**（test split D n=1）。
- release 实测：manifest 在 `git_dirty=true`、HEAD=`1f2b341`（V1）时仍生成，无 code hash/artifacts；`audit/releases/` 不存在。

## 最小放行条件（不改代码，仅要求）

1. 把 V2 全部资产提交到 `architecture/research-v2`，保证工作区干净；冻结 commit 后再 QA。
2. release manifest 增加 code hash、config/data hash、scan_id、真实测试命令/输出/hash/artifact、feature/detector version；拒绝 dirty tree 和 `scan_runs.status!=success`；不要覆盖同一 commit 的旧 manifest。
3. 修正 macro anomaly 的 `date=observation`、`available_date=availability`，evidence 写 `observation_date`；用真实 FeatureBuilder 的测试覆盖。
4. 候选 schema 加 `evidence_for/against` 与 A/B/C/D IDs；validator 校验来源、`available_at<=as_of`、hypothesis 唯一、falsification 与 hypothesis 的对应；修复 H3 恒真、priority_key 死代码、tier/排序与阈值任意性。
5. 给 V2 增加 CLI handoff 入口与 fake-CLI 全状态矩阵；修 L2-only 判定和 timeout/unknown 持久化；fact sanitizer 不得改写事实方向。
6. evaluation test split 至少 n>=3（并满足 pre-registered rule）才可能 `VALIDATED`；当前保持 `NOT VALIDATED`，不得用 development/validation 的 1.35/0.60 替代 test 结论。
