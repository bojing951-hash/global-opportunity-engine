# RESPONSE TO FINAL QA ROUND 2

QA verdict: PASS WITH ISSUES; two P1s. Both fixed after the report was written.

## P1-1 — a single stale optional series globally disabled deep research
- Finding: `readiness.degraded` was true for any stale macro (US_CAPE, EA_HICP), and
  `OpportunityEngine(data_degraded=True)` capped **every** candidate at watch. With score<0.68
  nothing was deep anyway, but the explanation "0 deep is the strict gate" was partly wrong.
- Fix: `ReadinessResult` now separates `degraded` (disclosure: any stale series/region)
  from `critical_degraded` (broad macro/curve failure). Pipeline passes only
  `critical_degraded` to the candidate gate. Single stale series stays visible in the report
  and in candidate data-quality gaps, but does not globally cap research.
- Verification: real final scan `degraded=True (EA_HICP stale)`, `critical_degraded=False`;
  `test_single_stale_series_is_disclosure_not_global_deep_cap`; `test_data_degradation_caps_deep_research`
  still proves broad degradation caps.

## P1-2 — all tenors of one core curve stale were not critical
- Finding: the old check aggregated all curve systems; deleting UST recent rows left other systems
  fresh, so `fresh_curve>0` and no critical.
- Fix: per-curve-system check. If a system has present tenors and zero fresh tenors → critical
  (`"UST 曲线全部过期…"`); if <50% fresh → degraded warning. Still no global aggregate-only test.
- Verification: `test_stale_curve_is_critical_not_silent` deletes UST recent rows and asserts
  `ok=False` with a curve critical; synthetic fixture covers it.

## Remaining P2s (documented)
- 1–2 instrument markets with stale data: warning, not critical (CA now warns; small market cannot
  invalidate the whole scan). Region with >=3 configured instruments is critical.
- Blind evaluation fact asymmetry: engine-selected objects carry more mechanism tags; the rater
  can reward that. `audit/RESEARCH_QUALITY.md` states this explicitly and calls the +0.021
  advantage over anomaly ranking not an independent selection proof.
- Docs/test counts and old top-3 numbers were stale; final numbers are 137 tests, 1,511 anomalies,
  11 candidates (3 watch/2 low/1 invalidated/5 excluded), top scores 0.606/0.593/0.548.
- Final 7/7 replay artifact archived at `reports/validation_cases_20261114T063037Z.md`.
- `expected_outputs` in old examples refreshed by `goe export`; no "估值与赔率" wording remains in
  the current research task example.

## Not independently verifiable here
- Real CFTC/BLS publication timestamps and vintages.
- Human/expert blind labels and forward performance beyond the 12-object sample.
- A real `ok_valid` A→B research handoff (B still returns out_of_scope on asset-specific questions).
