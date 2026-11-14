# ROOT CAUSE ANALYSIS — rounds 1–2

| Symptom | Root cause | Local/systemic | Fix | Verification |
|---|---|---|---|---|
| CFTC as_of includes future row; net/OI = raw contracts | publication lag applied after truncation; OI series never loaded; missing OI silently fell back to raw net | systemic data layer | lag before truncation; OI required; missing OI → `net_to_oi` unknown | P1-03/04 tests; live −0.2048; new missing-OI test |
| Macro anomalies never trigger in 7-day window | observation date used for anomaly/trigger recency | systemic time semantics | availability dates + frequency windows (7/21/75/150) | time-semantics tests; M05 triggered by US_CPI |
| Historical replay values wrong (Nikkei −0.39% vs −23.11%) | one end-of-window FeatureSet reused; macro truncated by observation date | systemic validation | per-eval `slice_as_of`; macro indexed by availability | reproduction matches true PIT |
| 40% trend_break false signals | global-calendar `shift(10)` + `fillna(0)`; detection pre-truncated at window start | systemic detector design | per-instrument valid observations; detect on full history then filter | 1,181→93; boundary regression test |
| Monday/post-holiday returns missing; breadth dead | union calendar (crypto weekends) used for row-based returns/MA200 | systemic feature calendar | business-day panel; per-instrument returns; valid-observation windows | SPY 11-09 z=3.35; breadth anomalies 17 |
| Gap was a constant / missing data scored positive | no measurement of expectations; `None` treated as 0 | systemic research method | measured proxies; explicit None; deep gates | gap components shown; missing-gap test |
| Gap "current" was 2026-10-30 while as_of 11-12 | `sample.iloc[::21]` last grid row used as current | local implementation | current = latest common valid row; stale >10d unavailable; record lag/n_obs | R2 audit reproduction; gap dates now 11-12 |
| Same asset/theme in multiple archetypes | theme dedupe keyed by archetype; policy/event drafts lacked theme | systemic ranking | one object per theme across archetypes; add themes | no duplicate primaries in scan |
| Past events scored as ≤10-day catalyst | `days<=10` did not require days≥0 | local scoring bug | forward-only catalyst windows | past-catalyst test; QQQ score drops |
| Own invalidation conditions ignored for re-detected candidates | lifecycle `continue` when fingerprint current | systemic falsifiability | evaluate checks for current candidates too | current-invalidation test; VIX candidate invalidated |
| Mechanism direction contradicted by asset | `expected_direction` stored but never read | systemic research logic | skip low-confidence contradictions; flag/cap stronger ones | XLP expected down/+5.8% removed |
| Weak mechanism got full breadth/evidence quality | breadth from asset count; evidence_quality ignored counter-evidence/mechanism | local scoring | confidence-weighted breadth; counter-evidence/mechanism term | config/docs/code aligned |
| A→B "success" on refusal | parser only checked run_ok/evidence count | systemic handoff contract | S8 status answered required; out_of_scope → refused; L1/L2 counts | parser tests; real handoff now refused |
| Silent detector crash produced successful scan | pipeline ignored `anomalies.attrs["errors"]` | systemic reliability | raise + rollback on detector errors | fault-injection test |
| Failed scan could leave DB half-written | per-method commits; no outer transaction | systemic DB contract | SAVEPOINT-aware `Store.transaction` + one scan transaction | report-failure/detector-failure rollback tests |
| Dead market hidden by global coverage; macro freshness false alarm | global-only coverage; latest un-published print treated stale; future-dated rows counted | systemic data health | per-region configured/tracked/fresh; latest AVAILABLE obs; critical curve; wall-clock fixed | readiness adversarial tests |
| Futures roll gaps can look like anomalies | continuous front-month series without contract metadata | data limitation | flag every futures candidate, dq penalty, disclose; no false precision | roll-risk field/evidence; documented |

---

# Round 3 root causes

| Symptom | Root cause | Fix | Verification |
|---|---|---|---|
| Historical bar changed with as_of (CSI300 3703 vs 4017) | completeness compared clock hour of fetch to bar-date close even when fetch was a later backfill; only last bar checked | same-session-only check, DST-aware local close, all bars, pre-action basis for splits | real t/T exact; CSI300 4017.855; DST/split tests |
| A→B failed process recorded completed | parser reused stale artifacts; persist/CLI used semantic only; ok_valid ignored empty evidence | clear out_dir, mtime check, S8 answered + evidence required, status gates | fake IA matrix + real refused task |
| 1/125 provider rows still success | status only looked at rows>0/errors, not target coverage; report meta omitted ingest | coverage-based ingest status, blocked_data, meta/ingest disclosure | 1/125 → failed/blocked |
| Readiness refreshed by intraday bar | readiness used raw first row instead of completed-bar rule | readiness computes last complete bar via `bar_is_complete` | 10-day dead market + partial bar blocked |
| Crypto bad print bypassed cleaning | native calendar captured before cleaning | clean native series independently, dedupe issues, same-day bar partial | bad crypto test; weekend test |
| Macro PIT slice lost stale series | `_load_macro` dropped series based on T staleness | keep history, flag stale | 5.77M rows exact |
| Excluded never recovered | excluded treated terminal | auto re-arm allowed and tested | excluded→watch test |
| Policy narrative top-1 | BIS availability date treated as event catalyst | no catalyst, age disclosure, >10d low_priority | top now DXY/N225; policy low 0.603 |
| DAX fake watch | local driver used SPY, not SX5E/EUR | local index/FX drivers | DAX 0.529→0.514 low |
