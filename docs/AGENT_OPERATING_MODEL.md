# Multi-Agent Operating Model (V2)

## Roles (real subagents when available; otherwise separate workflow stages)
| Agent | Owns | Must not |
|---|---|---|
| 0 Chief Architect | requirements, contracts, task DAG, freeze/release decision | write the code being audited at freeze time |
| 1 Data Architect | data/time/quality contracts, source verification, per-market health | change research hypotheses |
| 2 Quantitative Researcher | independent math, statistical validity, PIT property, benchmark implementation | accept a metric without independent recomputation |
| 3 Global Macro Researcher | competing hypotheses, transmission logic, research worthiness, decision impact | turn a corr relation into a causal/mispricing claim |
| 4 Software Engineer | implementation, DB, CLI, integration, tests | self-approve release |
| 5 Test Engineer | contract tests, real-data tests, fault injection, reproducibility | weaken thresholds or delete failing tests |
| 6 Independent QA / Red Team | adversarial audit on a frozen commit/snapshot, veto | edit the audited tree or re-run same tests only |

## Execution sequence (contract first)
1. Requirements → update `contracts/*` and acceptance tests.
2. Implement on `architecture/research-v2` (or a child branch).
3. Run unit/integration/real-data/fault tests; record artifacts.
4. Freeze: commit + config_hash + data_hash + scan_id + test count; write a release manifest.
5. QA on the frozen commit/data; every finding needs a failing reproduction.
6. New commit fixes; re-freeze; re-QA. Two consecutive QA passes with new fault inputs are required
   for engineering sign-off.
7. Research validation is separate: A/B/C/D blind evaluation on fixed splits; if D does not beat
   baselines, output NOT VALIDATED. No weight tuning on the test split.

## Freeze/QA rules
- QA never modifies the frozen tree; fixes go to a new commit.
- QA must pin data snapshot, code hash and config hash; do not mix versions.
- Old V1 scoring/results remain available as a control (`v1-frozen-1f2b341` tag).
- Research candidates must remain in A even when B refuses; handoff failure never drops them.

## Deliverable IDs
- Contracts: `contracts/`
- Evaluation protocol/input/results: `evaluation/`
- Release manifests: `audit/releases/`
- Research cards: `exports/research_candidates_<as_of>.json`
- V1 freeze: `audit/V1_FREEZE.md`
