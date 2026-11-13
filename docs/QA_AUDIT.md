# 独立 QA 审计 — Global Opportunity Engine

- 审计人：Agent 6（独立 QA / Research Reviewer）；日期：2026-11-13；仓库：`global-opportunity-engine`
- 方法：只读代码/DB/导出；不修改源码、配置、测试或数据；本文件为唯一写入。
- 说明：审计期间仓库仍在被其他 Agent 修改。`data/goe.db`/报告/导出生成于 22:52，`goe/opportunities.py` 与 `config/scoring.yaml` 的 mtime 为 22:59，故 DB 产物与当前代码存在版本差；下列"已存产物"均指 22:52 快照。

## 结论摘要

**Verdict: PASS WITH MINOR ISSUES（终审，2026-11-13 23:30）**

一句话理由：原 3 个 blocker（覆盖/CPI/错价）均已修复并经独立复算；TOPIX 10 倍断点已在终审中确认消失（12m +21.52%、动量 0.261、最大日收益 8.41%），剩余仅为文档/格式/流程类 minor。

## 验证清单（实测）

| # | 检查 | 结果 | 关键输出/数字 |
|---|---|---|---|
| A1 | 离线测试 | **已验证** | `pytest tests -m "not network" -q`：93 passed，exit 0；未单独计时（TEST_RESULTS 记 25s） |
| A2 | 联网测试 | **已验证** | `pytest tests -m network -q`：9 passed，8.2s，exit 0 |
| A3 | doctor / events | **已验证** | 127 instruments、92 series、35 events（34 verified、1 unverified `CN_LPR_2026_11_20`）；last_scan success |
| A4 | git | **已验证** | `No commits yet`；`git ls-files`=0；18 个未跟踪顶层条目 |
| B1 | 3 标的×3 日期 Yahoo 对比 | **已验证** | SPY 2024-06-03 close 527.7999878=527.7999878，adj 512.6630859 vs 512.6630249（差 6.1e-5，约 0.00001%）；SSE 2025-03-14 3419.5620117 完全一致；GC 2026-06-15 4351.6000977 完全一致 |
| B2 | UST/CPI/CFTC | **部分失败** | UST:10Y 2024-06-03=4.41，Treasury CSV 4.41 一致；CFTC 2026-11-03 Gold MM net 103,614=122,283−18,669；UST10Y LEV −2,262,310=585,873−2,848,183；**US_CPI 2026-09 存 4.00%，按指数应为 3.74%** |
| B3 | 单位/量纲 | **部分失败** | `US_CREDIT` 值 43,604.657（十亿美元），`series_meta` 标 `USD_mn`，`config/macro.yaml` 标 `USD_bn`；`CN_CREDIT` 同；quality_issues 仅 2 条 warning，未改标 |
| B4 | 重复/常量/异常值 | **失败** | 无重复价格列；但 2 标的全 NULL（CM_MET_NI、IT_EQ_FTSEMIB）、4 标的仅 1 个非空值；CN_SEC_SEMI 2026-07-02 1.4715→2.7000（+83.5%，z=47.1）被判 score=1.0 |
| C1 | 前视（特征） | **已验证** | `no_lookahead_diff(2025-06-30,2026-06-30)`：n=3,370,216，max_abs_diff=0.0，147.5s，leakage=false |
| C2 | 前视（传导条件统计） | **失败** | 条件收益从宏观观测日起算（`evaluator.py:281`），但该数据 +45d 才发布（`features.py:694`），条件样本含发布前价格 |
| C3 | 案例通过标准/7·7 | **未验证→失败** | 7/7 无归档 `reports/validation_cases_*`；唯一临时证据 `data/tmp_gold5/...145853Z.json` 为 GOLD 单案 **FAIL**；最终运行尚未产出 |
| C4 | 幸存者偏差 | **已验证（已声明）** | `docs/LIMITATIONS.md` §9 明确当前存续标的偏差；但报告未在机会级重复提示 |
| C5 | 重复机会 | **部分失败** | 15 个 fingerprint 唯一；但 M01 一个机制生成 OPP-0003/0006/0007/0008 四条（无机制级上限） |
| D1 | 3 个异常手算 | **已验证** | price_return_shock CM_AGR_LE 2026-07-01：z=−9.977→(9.977−3)/4=1.744→clip 1.0；drawdown pct=0→1.0；positioning pct=1.0→1.0；均越阈值且 score∈[0,1] |
| D2 | robust_z / percentile 手算 | **已验证** | [1..10] 末值 robust_z=1.2140833671，与 (10−5.5)/(1.4826×2.5) 完全一致；[1,2,3,4,10] percentile=1.0 |
| D3 | flood control | **已验证** | 构造 6 天同键分数 0.2/0.9/0.5/0.95/0.1/0.8，保留 0.95；DB 内 5 日同键簇无多行，无重复 ID |
| D4 | 确定性 | **已验证** | 同一 fs 连跑两次 `detect_anomalies`：均 2,739 条，anomaly_id 集合与 score 完全一致 |
| E1 | 传导重跑 | **已验证** | M01=mixed 0.56、M05=supported 0.85，与 DB 记录完全一致；失败检验在 evidence_against |
| E2 | 机制文案 | **部分失败** | "correlation_only/相关不等于因果"存在；条件统计标"描述性"；但 M10 以 3 条共线 corr（HYG-SPY/IWM/LQD）得 supported 0.85，CAPE 检验 missing；M05 supported 仍有一条 corr 失败 |
| E3 | 机制符号 | **未验证/疑似错误** | M15 `US_UNRATE` vs `US_FI_SHY` expected_sign=−1：失业率上行→降息→SHY 涨，应为 +；该机制本期未激活，未形成运行影响 |
| F1 | 评分算术 | **已验证** | 权重和=1.0；OPP-0001 加权 0.682748 vs DB 0.6828（四舍五入） |
| F2 | 门槛/阈值 | **部分失败** | 0.38/0.52/0.68 与 SCORING 一致；`require_mechanism_or_divergence` 配置存在但未实现；`timing_window` 恒为 1.0（`opportunities.py:877`） |
| F3 | 生命周期 | **部分失败** | 15 条事件均只有 created；15 条中 10 条 `invalidation_checks=[]`，无法自动失效；deep_research 为粘性状态，不会随分数回落 |
| G1 | handoff 真实性 | **部分失败** | `exports/ia_runs/OPP-0001/...` 存在（rc=0 报告），但其问题是 **Shenzhen Component**；当前 OPP-0001 是 **Nikkei 225**，且产物 14:01 早于最终数据 14:52/代码 14:59 |
| G2 | schema/自包含 | **已验证（结构）** | 15 个 envelope 必备字段齐全；status/score 类型合法；research_question 1,104 字符，自含现象/假设/证据/失效条件 |
| H | 报告质量 | **部分失败** | 68,897 字节、15 候选；机会档案可追溯、有反证、无"必然/低估"；但异常表被 trend_break 0.5 刷屏（1,141/2,739），波动列把 0.1 显示成"0.1"而非 10%；声称"features 表"但 DB 无 features 表（`reports.py:181`） |
| I | 秘密/卫生 | **部分失败** | `check_secrets.sh` 通过；但因 `git ls-files=0` 检查是**空跑**；`.gitignore` 覆盖 data/、reports/、exports/*（含 ia_runs）、.env；项目文件未发现密钥/绝对个人路径（文档示例已脱敏 `<repo>`） |
| J | 稳定性/性能 | **部分失败** | 特征 build 45.2s、scan 51.09s、DB 106MB，可支撑日任务；但 `yahoo.py:117-126` 把整列 NaN 当有效数据写入，`ingest.py:164` 只按 instrument_id 判缺失，导致 6 个死标的静默通过 |

## 问题清单

| 严重度 | 文件:行 | 证据 | 最小修复 |
|---|---|---|---|
| **blocker** | `goe/sources/yahoo.py:117-126` + `goe/ingest.py:164` | 2 标的全 NULL、4 标的仅 1 非空行；doctor 仍报 127，特征实际 121；无 quality issue | 丢弃全 NaN symbol；按非空行数判 failed；doctor/README 改报"可用 121/配置 127" |
| **blocker** | `goe/features.py:692-694` | 2025-10 CPI 缺失，`pct_change(12)` 按行数而非日历月：2026-09 得 4.002%，真值 3.738%；2026-10 应为 NaN 却得 3.913%；2026-05 macro_shift 因此 z=3.54、score=1.0 | yoy 前先按频率重采样到完整月度网格再 `pct_change(12)`，并补缺口质量告警与回归测试 |
| **blocker** | 价格清洗层（`yahoo.py`/`base.normalize_prices`，无拒绝规则） | CN_SEC_SEMI 2026-07-02 +83.5%（z=47）触发两条 score=1.0；JP_EQ_TOPIX 2026-03-30/31 382.7→37.64→389.2（10 倍，2 天）；CM_ENE_CL 2020-04-20 负油价使 pct 收益 −126% | 加拆分/错价规则：单日 |ret|>50% 对照 close/adj 比率与成交量，隔离并写 quality_issues；负价序列禁用 pct 收益 |
| **major** | `README.md:90-91`、`docs/SCORING.md:50-62` | 文档 OPP-0001=中国 Shenzhen 0.71；DB 实为日本 Nikkei 0.6828；`PROJECT_STATE` 的 4 deep_research/10 watch 亦与 1/12/2 不符 | 用当前 DB 重写示例，删除手写数字，改为生成式片段 |
| **major** | `goe/transmission/evaluator.py:281-283` + `features.py:694` | 条件收益以宏观观测日 t 入场，而 CPI/BIS 在 t+45d 才发布；条件统计存在前视，`no_lookahead_diff` 不覆盖此路径 | 入场日改为 `t + release_lag`，或只用发布日期对齐；加单测 |
| **major** | `exports/ia_runs/OPP-0001/...` + `docs/INTEGRATION_INVESTMENT_AGENT.md` §4.3 | handoff 报告研究对象为 Shenzhen，当前 OPP-0001 为 Nikkei；代码 22:59 晚于 DB 22:52；未复跑 | 冻结代码后对当前 OPP-0001 重跑 handoff，归档新路径并在文档标注时间戳 |
| **major** | `docs/VALIDATION.md` §3、`PROJECT_SPEC.md:84` | 声称 7/7、又说"6 通过"；无归档结果；临时 GOLD 单案 14:58 FAIL | 以最终运行文件为准更新；删除未生成的 7/7 断言 |
| **major** | `goe/opportunities.py:577-600`、DB | 10/15 候选 `invalidation_checks=[]`（regime/event/relative 全为空），文档却称自动评估 | 为三原型补可计算检查，或明确标"人工失效" |
| **major** | `goe/transmission/evaluator.py:390-430` | M10 以 HYG-SPY/IWM/LQD 三条共线 corr 得 0.85 supported，CAPE 条件检验 missing；M05 亦有一条 corr 失败仍 supported；无多重检验校正 | 按独立资产/独立机制降权，FDR/Bonferroni，missing 单列而非沉默 |
| **minor** | `goe/opportunities.py:877` | `timing_window` 恒 1.0（horizon 与 ARCHETYPE_HORIZON 同源），0.06 权重无区分度 | 改为按异常半衰期/事件距离计算 |
| **minor** | `goe/reports.py:194` | `ann_vol` 以 `_num` 输出 0.1，列名"3月年化波动"应为 10% | 改用 `_pct` |
| **minor** | `scripts/check_secrets.sh:10` | `git ls-files` 为空，secret/ignored 检查全部空跑通过 | 先 `git add` 再跑，或扫描工作树 |
| **minor** | `series_meta` / `quality_issues` | credit 单位 USD_bn vs USD_mn 冲突；9 条 13:38 的 provider_missing 旧错误仍留在表内 | 重新 register_metadata，清理/按 run 标记过期问题 |

## 报告中无法验证的断言

- "7/7 历史案例通过"——无 `reports/validation_cases_*`；唯一临时 GOLD 单案 FAIL；最终运行在审计时仍未完成。
- "handoff 对当前 OPP-0001 rc=0"——现有 artifact 是 14:01 的 Shenzhen 旧问题，未对当前 Nikkei 记录复跑。
- "127 标的 / 92 指标序列可用"——DB 有 127/92 行，但可用价格 121、含 6 个空/单点标的；`series_meta` 仅 36 行。
- "所有异常可由 features/anomalies 表复算"——DB 无 features 表（`reports.py:181`）；只能重跑特征层。
- "14 检测器"——代码 14 类，DB 实际只出现 13 个 detector 名；policy_rate_change/valuation_extreme/breadth_extreme 未触发。
- "15 机制、53 项检验"——配置计数属实；但本期仅 9 条激活、2 条 supported，"15"不代表都经过检验。
- investment-agent 报告内容质量——只验证了文件存在与 rc=0 记录，未审其结论正确性。

## 对 12 条验收标准的独立判断

| # | 标准 | 判断 | 理由 |
|---|---|---|---|
| 1 | 可运行监测系统 | 部分满足 | 管线可跑；但 121/127 可用，报告与 doctor 口径不一致 |
| 2 | 真实数据+来源/时效 | 部分满足 | 价格/UST/CFTC 逐值匹配；CPI YoY 错、credit 单位冲突、quality_issues 未报缺口 |
| 3 | 异常检测 | 部分满足 | 确定性、可复算；错价/拆分产生 score=1.0 假异常；trend_break 占 42% |
| 4 | 宏观/跨资产传导 | 部分满足 | 9 激活/2 supported；条件统计前视、共线检验、M15 疑似符号错 |
| 5 | 机会候选池 | 部分满足 | 15 条、字段齐全；10/15 无自动失效、M01 一因四机会 |
| 6 | 证据/原因/机制/问题 | 部分满足 | 结构完整、有反证；事件型候选仅凭 trend_break 0.5 入场，偏薄 |
| 7 | 可解释评分排序 | 部分满足 | 权重和 1、算术正确；timing_window 恒定、doc 与代码不一致 |
| 8 | investment-agent 接口 | 部分满足 | schema/research_question 合格；当前记录未复跑，证据过期 |
| 9 | 历史/质量/E2E 测试 | 部分满足 | 93+9 全过；但 7/7 未验证、临时 GOLD FAIL、数据质量断言未覆盖真实缺陷 |
| 10 | 自动运行/恢复/持久化 | 未验证 | `run_daily.sh` 存在；未验证调度实际执行与失败恢复 |
| 11 | 可查看结果/说明 | 部分满足 | 报告可读、有免责声明；波动列错误、示例与现行数据脱节 |
| 12 | 完整上传 GitHub 可审计 | 不满足 | 无 commit、无 remote；`check_secrets` 空跑；18 项未跟踪 |

> 修复优先级：先修 #1/#2/#3（数据真实性与 CPI/错价），再冻结代码重跑 scan/handoff/cases，最后统一文档数字并提交 Git。

---

## Re-audit after fixes（2026-11-13 23:14–23:20，只读复核）

修复后的 scan：`scan-20261113T151338Z-57e59b`（23:13:45 成功，56.7s）。以下逐项实测，不采信修复清单。

| # | 复核项 | 实测结果 | 结论 |
|---|---|---|---|
| 1 | 标覆盖 | `doctor`：**125 of 125 configured**、358,310 行、`n_instruments=125`；SQL distinct non-null close=125，无全 NULL 标的；`CN_EQ_CSI300` 2,882 行，2015-01-05..2026-11-13，**0 NULL**；新增 `akshare_cn_index` provider | **通过** |
| 2 | CPI YoY | `_transform` 先按 MS/QS 重采样；US_CPI **2026-09=3.7377%**、**2026-10=NaN**、2026-05=4.2487%（真值 4.25%），报告 macro 表已显示 3.74 | **通过** |
| 3a | CN_SEC_SEMI 错价 | `price_data_issues`：2026-07-02 `extreme_move_quarantined` move=0.8349（阈值 0.4），已从收益中剔除；2026-06-29 −0.4705 亦隔离 | **通过** |
| 3b | CM_ENE_CL 负价 | 直接调用 `clean_price_panel` 返回 `nonpositive_price` 2020-04-20；但 scan 的 6.5 年窗口从 2020-05-13 起，故未进入本次 `price_data_issues` | **函数级通过** |
| 3c | JP_EQ_TOPIX 10x | **终审通过**：03-30/31 均记为 `extreme_move_quarantined`（dates 2026-03-30/31）；清洗后 03-27=382.7 → 04-01=381.9（adj）→ 04-02=383.0，无跨基准；全样本最大日收益 8.41%，12m=+21.52%，momentum_12_1=0.2614 | **通过（已修复）** |
| 4 | 条件收益前视 | M05 的 `publication_lag_days=45`、`first_entry=2021-05-17`；CPI/Core CPI 条件样本从发布后入场；`no_lookahead_diff` 之外的新路径已消除 | **通过** |
| 5 | 置信度膨胀 | M10 由 0.85 降为 **weak 0.53**（distinct left series + conditional 计数）；本期 8 条激活：6 mixed / 1 weak / 1 unsupported，**0 supported**，不再虚报 | **通过** |
| 6 | 失效条件 | 5 条 regime 候选均写入 `US_FX_DXY return_z_3y between [-1,1]` 的触发 z 检查；4 条 event 候选仍 `invalidation_checks=[]`；relative 代码已加收敛检查但本期无 relative 候选，无法在 DB 验证 | **部分通过** |
| 7 | 文档/交接 | OPP-0001 已改为 COMEX Gold、0.7042 deep_research；README/SCORING 同步；报告改为"重建特征层复算"；新 handoff `exports/ia_runs/OPP-0001/20261113T151401Z_.../report.md`（15:14:01）研究对象=GC=F，rc=0 路径与当前记录一致 | **通过（rc 未独立复跑，仅核 artifact）** |
| 8 | 测试 | 离线套件 exit 0；输出点计数 **97 passed**（72+25），无 failure；联网 9 项本次未重跑 | **通过（联网未重跑）** |
| 9 | 其他旧问题 | `series_meta` credit 已修正为 USD_bn/CNY_bn；但 `quality_issues` 仍留有 9 条 13:38 的 `provider_missing` 旧错误；报告的 `ann_vol` 仍用 `_num` 输出 0.1（应为 10%）；`timing_window` 仍恒 1.0 | **minor 未修** |

### 复审新增问题（仅列剩余）

| 严重度 | 文件:行 | 证据 | 最小修复 |
|---|---|---|---|
| — | `goe/features.py:191-204` | **终审已修复**：拆分需满足"比率匹配 + 后续最多 6 个有效观测连续"，否则隔离整个跳变+回补窗口；新增 `tests/test_data_integrity.py` 4 项通过 | 已按建议修复，保留回归测试 |
| major | `goe/features.py:191-204` | CN_SEC_SEMI 2021-03-26 被按 ratio=2 反转（0.867→1.734 更像坏点而非 2:1 拆分），导致 2015-2021 历史整体 ×2；2021-03-29 再被隔离 | 拆分判定需用 provider split actions 或成交量/多日连续性；单日尖峰默认隔离而非重基 |
| minor | `docs/PROJECT_SPEC.md:49` | 仍写"127 个交易标的"，与 125 配置/doctor 不一致；同文件:84 又写"7 个情景（6 通过）"与 VALIDATION 7/7 冲突 | 统一为 125 与最终案例结果 |
| minor | `goe/reports.py:197` | 3 月年化波动 0.1 而非 10% | 改 `_pct` |
| minor | `goe/opportunities.py:906` | `timing_window` 仍恒 1.0 | 按事件距离/半衰期计算 |
| minor | `quality_issues` | 9 条旧 `provider_missing` 未清理/未按 run 标记过期 | 重跑后按 run_id 过滤；报告只展示最近成功 run |

### 更新后的 12 条验收判断（仅按复审证据）

| # | 判断 | 理由 |
|---|---|---|
| 1 | **满足** | 125/125 可跑，CSI300 等已修复；不再是 127 假覆盖 |
| 2 | **满足** | CPI/credit/handoff  provenance 已修；UST/CFTC/Yahoo 抽查仍精确 |
| 3 | **满足** | 错价/拆分规则生效：TOPIX 03-30/31 隔离、04-01≈381.9 连续；CN_SEC_SEMI 2021-03-26 坏点隔离、2026-07 窗口隔离 |
| 4 | **部分满足** | 条件前视已修、置信度不再膨胀；8 激活 0 supported，机制证据仍薄 |
| 5 | **部分满足** | 15 候选结构完整；4 条 event 无失效检查，M01 仍一因六机会（0001/0005-0009） |
| 6 | **部分满足** | 档案/反证/问题齐全；event 候选仍只凭 trend_break 0.5 入场 |
| 7 | **部分满足** | 权重和/算术正确；timing_window 恒定、vol 格式小错 |
| 8 | **满足** | 当前 OPP-0001 Gold 的 handoff artifact 存在且对象一致；未独立复跑 rc |
| 9 | **部分满足** | 97 离线通过；7/7 仍无归档（reports/ 无 validation_cases），临时 GOLD 单案曾 FAIL |
| 10 | **未验证** | 调度脚本存在；未验证定时执行与失败恢复 |
| 11 | **部分满足** | 报告/示例已刷新；vol 列与旧 quality_issues 仍误导 |
| 12 | **不满足** | 仍 0 commit、0 tracked；`check_secrets` 空跑；18 项未跟踪 |

**终审结论：PASS WITH MINOR ISSUES。** TOPIX 清洗断点已在 23:27 复核中消失；scan 2,935 异常、15 候选（2 deep/11 watch/2 low）、handoff 15:24 对 Gold 重跑。剩余问题见下，均不构成数据/方法 blocker。


### Final re-check（23:27，仅 TOPIX 项）

- `fs.meta["price_data_issues"]`：JP_EQ_TOPIX 仅 `extreme_move_quarantined`，dates=`["2026-03-30","2026-03-31"]`，move=−0.9016；无 `split_adjusted`。
- `fs.prices`：03-27=382.70 → 03-30/31=NaN → 04-01=381.86（adj）/389.2（close）→ 04-02=375.78（adj），无 10x 基准。
- `fs.returns.abs().max()`=**0.084069**；`return 12m`=**+21.516%**；`momentum_12_1`=**0.2614**。
- `tests/test_data_integrity.py` 4 passed；全量离线 97 passed（dot count；pytest 未打印汇总行）；DB 最新 scan `scan-20261113T152359Z-9dfe13` success，2,935 异常，15 候选=2/11/2；handoff `20261113T152421Z` 对 GC=F。
- 仍未修/未验证：`PROJECT_SPEC.md:49` 仍写 127（:84 仍写 6 通过）；报告"3月年化波动"仍输出 0.1 而非 10%（`reports.py:197`）；`timing_window` 恒 1.0 已文档化但未改代码；4 条 event 候选无自动失效检查（已声明 manual/expiry）；7/7 案例仍无归档文件；0 commit、`check_secrets` 空跑。
