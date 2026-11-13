# AGENTS.md — 给后续 AI Agent / Claude Code 的工作约定

> 本文件面向**修改本仓库**的 AI Agent。人类请读 README.md。

## 必读顺序

1. `README.md` — 系统做什么、如何运行
2. `PROJECT_SPEC.md` — 目标、范围与验收标准
3. `ARCHITECTURE.md` — 模块与数据模型
4. `DECISIONS.md` — 关键取舍（改动前先看是否已有决策）
5. `PROJECT_STATE.md` — 当前进度与阻塞
6. `docs/LIMITATIONS.md` — 已知缺口，不要把缺口当结论
7. `docs/SCORING.md`、`docs/VALIDATION.md` — 评分与验证方法

## 硬性纪律

- **不伪造数据、不引入未来信息、不把模拟数据写成真实结论。**
- 数据源只允许公开、免密钥接口；不得绕过付费墙或抓取未授权数据。
- 不修改 `investment-agent` 仓库；集成只通过 `goe/integration/` 的 JSON + CLI。
- 关键计算必须有测试；新增检测器/机制/评分维度必须同步更新文档与 tests。
- 提交前运行：`make test`（离线）、`make doctor`、`python -m goe.cli events --check`。
- 运行库 `data/goe.db`、`reports/`、`exports/ia_runs/`、`.env` 不得提交（见 .gitignore）。

## 常用命令

```bash
.venv/bin/python -m goe.cli doctor
.venv/bin/python -m goe.cli scan --no-ingest
.venv/bin/python -m goe.cli replay --cases
.venv/bin/python -m pytest tests -m "not network" -q
.venv/bin/python -m goe.cli handoff --ia-path ~/investment-agent-dev --limit 1 --dry-run
```

## 修改指南

| 想改什么 | 位置 | 必须同步 |
|---|---|---|
| 标的池 | `config/universe.yaml` + `config/themes.yaml` | `docs/id_reference.md` 重新生成 |
| 数据源 | `goe/sources/<name>.py` + `registry.py` + `config/sources.yaml` | 离线解析测试 + `docs/DATA_SOURCES.md` |
| 异常检测 | `goe/anomalies.py` + `config/thresholds.yaml` | 阈值边界测试 + 证据字段含公式 |
| 传导机制 | `config/mechanisms.yaml` | 触发 id 存在、≥1 个 corr 检验、反证条件 |
| 机会原型/评分 | `goe/opportunities.py` + `config/scoring.yaml` | `docs/SCORING.md` + 评分测试 + 历史回放 |
| 交接格式 | `goe/integration/exporter.py` | `HANDOFF_SCHEMA.json` 版本号 + 适配器测试 |

## 完成任务的定义

不是"代码写完"，而是：测试通过 + 真实数据跑通 + 报告/导出可查看 + `PROJECT_STATE.md` 更新 +
在 `DECISIONS.md` 记录取舍。若某数据/接口不可得，明确写入限制，不得用模拟结果替代。
