# QA — Evidence / Release Engineering（独立复核）

- Date: 2026-11-15
- Frozen HEAD: `d914628`（code `c4b89ad`），branch `architecture/research-v2`
- Verdict: **PASS WITH ISSUES**
- Remaining P0: 0；Remaining P1: 1（CI 从未在 GitHub runner 实跑，已诚实披露，非虚假声明）

## 1. CI workflow

`.github/workflows/verify-release.yml`：YAML 解析通过；`actions/checkout@v4` + `fetch-depth: 0`（`verify-release` 需要祖先历史）；Python 3.12；安装 `-e . pytest`；`ls -1t audit/test_evidence/*.proof.json | head -1` 选最新 proof；执行 `python -m goe.cli verify-release --proof`。权限 `contents: read`，失败即红（fail-closed）。

- **未在真实 GitHub runner 上执行。** `audit/CI_REPLAY.md` 明确写 “Not yet executed on GitHub Actions”；GitHub API 查询被 403 rate limit 挡住，无法看到 workflow run。远端 `origin` 存在，但本次不能声称 CI 通过。→ **P1（验证缺口，已披露）**
- **P2**：fresh checkout 中所有文件 mtime 相同，`ls -1t` 取最新 proof 依赖检出顺序，可能选到旧 proof；好在 `verify-release` 会拒绝不兼容 proof（不会假绿），但 CI 可能无故变红。建议按 commit/文件名确定性选 proof。
- **P2**：actions 未 pin SHA（供应链惯例问题）。

## 2. Release proof / manifest（c4b89ad）

- proof `audit/test_evidence/20261115T022911Z_c4b89ad6c9.proof.json`：schema `goe-test-proof/v4`，`git_dirty=false`，`passed=208`，`required.count=executed.count=208`，两者 sha256 相同 `4fec60…d5a3`。
- junit：`tests=208 failures=0 errors=0 skipped=0`；log sha256 与 proof 一致 `017f26…e3a`；junit sha256 `868418…40e0` 匹配。
- **独立重放**：在 `/tmp` 干净 clone（HEAD `d914628`）执行 `verify-release --proof <c4b89ad proof>` → **accepted**：commit `c4b89ad`，208 passed，rerun `passed=208 executed=208 skipped=0`。`d914628` 相对 `c4b89ad` 只改了 4 个 audit 证据文件，符合 verifier 的 ancestor 规则。
- 本工作树 `/Users/cast/.../global-opportunity-engine` 当时因并行审计编辑 `audit/V2_FINAL_ACCEPTANCE.md` 变脏，本地重放报 “dirty worktree”；这是 QA 并发环境问题，不是提交本身的问题。`c4b89ad` 的 clean-tree 声明在干净树上成立。
- manifest `release_c4b89ad6c9.json` 的 `reports/report_2026-11-13.md`、`reports/scan_2026-11-13.json` sha256 实测与 manifest 完全一致。
- **P2**：manifest 的 `test_evidence.proof_path` 是 macOS 绝对路径，可移植性差（不影响验证逻辑）。

## 3. Cross-asset evidence 代码

- `goe/evidence/cross_asset.py` 只用传入的 `fs.returns`；`research_triage.run_triage` 用 `FeatureBuilder(store, as_of=as_of, point_in_time=True)` 构造，未发现用到 as_of 之后的数据；无合成/填充值。
- 观测不足（`< MIN_OBS=60`）→ `FactorFit.available=False` + reason；`evidence_for_bundle` 不写 `evidence_for`，`count_discriminating` 不计入；不会把“不可用”写成支持。测试 `test_cross_asset_insufficient_data_is_untestable_not_support` 直接断言该行为。
- 测试有真实断言（R²、discriminating、计数），非 tautology；但仅 2 条，**未显式覆盖**“returns 含 as_of 之后行时必须截断”以及 local/FX 分支 → **P2 测试缺口**（生产路径依赖 FeatureBuilder PIT）。
- **P2**：`compute_fits` 的 `as_of` 只用于标注，不自行裁剪；若未来调用方传入非 PIT FeatureSet，会静默引入未来数据。

## 4. Evidence gate 与 20 candidates

- `research_triage`：`count_discriminating` 只数 `status=="open"` 且 `evidence_for` 中 `discriminating=True` 且 `class!="unknown"` 的 hypothesis；`<2` → `tier=intelligence` + `research_readiness=evidence_gap`。
- `contracts.validate_research_candidate`：非 intelligence 必须 `research_readiness=="evidence_ok"` 且 discriminating≥2，否则 `ContractError`。
- 官方 artifact `evaluation/v2_candidates_20_2026-11-13.json`：**20 条**，`1 A (RC-20261113-12 N225, evidence_ok, 2 个 measured hypotheses) + 19 intelligence (evidence_gap)`，与声明一致；逐条调用 `validate_research_candidate` → **20/20 PASS**。
- 无删除/丢失：20 个 research_id 均在。N225 的 discriminating 来自 `H-EQJP-LOCAL` 与 `H-EQJP-FX`（各 1）。
- **P2（运行库卫生，非 release artifact）**：`data/goe.db`（gitignored）有 21 行，多出 2026-11-14 旧候选 `RC-20261113-21`（tier B、`research_readiness` 缺失），按新 contract 校验 **FAIL**。它不是本次 20 条 artifact 的一部分，也未被删除；说明 DB 会累积 gate 之前的旧行、缺清理/迁移。发布证据不依赖该 DB，故不升为 P1。

## 5. 外部适配器诚实性

- `consensus_evidence` / `ois_evidence` 均强制 `available_at <= as_of`，超过 `max_age_days` 返回 None；文件缺失/为空/列不全 → None；不插值、不造数。
- `config/evidence_sources.yaml` 默认 `enabled: false`；OIS `proxy: true`，注释明确 “FRED SOFR/2Y/10Y is a policy-path proxy, NOT a term OIS curve”；`docs/EVIDENCE_SOURCES.md` 同样写明 **Not term OIS**；实际 `data/policy_curve.csv` 的 source 列亦标注 proxy。
- Consensus 无公开许可历史数据，文档标 **BLOCKED**，仅 fixture 测试；未伪造。测试覆盖 PIT、stale、missing、disabled、仅 measured 时开 hypothesis，断言有效。
- **P2**：`ois_evidence(as_of, region=...)` 完全忽略 region，也不按 `series_id` 过滤；多区域/多 series 的曲线文件会把不同区域 tenor 混在一起算 2s10s。当前文件仅 `USD` 且默认关闭，无现实影响。

## 6. Targeted tests

`pytest tests/test_cross_asset_evidence.py tests/test_external_evidence.py tests/test_contracts.py` → **13 passed, 1 skipped**（skip 为既有条件跳过，非本次改动）。

## 结论

**PASS WITH ISSUES**。208 collected = 208 executed、proof 可独立重放、gate/contract/artifact 20 条一致、外部数据适配器 PIT 与诚实性成立、未发现新 P0/P1 代码缺陷。

Remaining P1：GitHub Actions 未真实执行（跨 OS CI 仍未验证；已披露，不能声称 CI 通过）。
Remaining P2：CI proof 选择依赖 mtime；actions 未 pin；cross-asset 缺显式 as_of 截断测试；OIS region 未过滤；manifest 绝对路径；DB 残留旧候选 `RC-20261113-21`。
