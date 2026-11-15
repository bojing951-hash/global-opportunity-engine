# QA_RESEARCH_CONFIRM — independent read-only confirmation

- Time: 2026-11-15 17:05–17:09 (Asia/Hong_Kong), timebox 3 min (slightly over)
- Repo: `global-opportunity-engine`, branch `architecture/research-v2`
- HEAD: `2488955` (release-proof commit); product code: `360b161`
- Mode: read-only; only this file written. No code/DB/artifact changes.
- Verdict: **CONFIRMED** — 20 candidates / 0 research / 4 watch / 16 archive / 0 eligible;
  N225 high/partial/watch; contract 20/20; A→B no task; quality audit is descriptive, not
  validation; **DISCOVERY VALUE: NOT VALIDATED**; **no new P0/P1** in scope.

## 1. Repo state
- `git status --porcelain` clean (before this report); HEAD `2488955db57c...`.
- `git diff --stat 360b161..HEAD`: only 4 release/proof artifacts
  (`release_360b1614d1.json` + JUnit/log/proof), **no product-code or test changes**.
- `release_360b1614d1.json`: `git_commit=360b1614d1...`, `git_dirty=false`, 231 passed /
  0 skipped, rerun 231; scan evidence counts 358,310 prices / 159,508 indicators / 1,506
  anomalies / 5 transmissions / 11 opportunities.

## 2. Current candidates (live `data/goe.db`, not just the frozen artifact)
All 20 payloads were read from `research_v2_candidates` and checked directly:

| dimension | counts |
|---|---|
| `research_queue` | research **0** / watch **4** / archive **16** |
| `priority_tier` | intelligence 20 |
| `research_worthiness` | high 1 / medium 3 / low 16 |
| `evidence_readiness` | ready 0 / partial 4 / missing 16 |
| `handoff_eligibility` | eligible **0** / a_retained 20 |

- DB `status` is `intelligence` for all 20; "0 research" is the research queue/tier result,
  not the raw `status` column. No discrepancy with the claim.
- Watch set: N225, TAIEX, QQQ, XLV.
- N225 `RC-20261113-JP_EQ_N225-455ff8e1a32f`: worthiness **high**, readiness **partial**,
  queue **watch**, eligibility `a_retained`, tier `intelligence`; 1 measured discriminator
  / 4 open hypotheses (coverage 0.25), `decision_value_flag=true`, but below the 2-measured
  research threshold.
- `goe.contracts.validate_research_candidate` on all 20 live payloads: **20/20 PASS,
  0 errors**.

## 3. A→B / handoff
- `research_v2_tasks` = **0**, `research_v2_results` = **0**, handoff-related
  `research_v2_events` = **0**. All 20 remain `a_retained`; no task was created.

## 4. Quality audit is descriptive, not validation
- `goe/research_quality.py` docstring explicitly says it is **not a valuation and not an
  independent performance label**, and fixes the only allowed verdict to
  `DISCOVERY VALUE: NOT VALIDATED` (`:8-11`, `:72`).
- `evaluation/RESEARCH_QUALITY_AUDIT.md:36` repeats: **DISCOVERY VALUE: NOT VALIDATED** —
  descriptive audit, no human/expert labels, no independent future window.
- Audit JSON matches: 20 candidates, 0 research, 4 watch, 0 eligible, mean coverage 0.075.
- Does not by itself establish discovery/alpha/mispricing; the current docs do not claim it.

## 5. P0/P1 assessment
- Prior independent QA (`audit/QA_IDENTITY_FINAL.md`, written against code `9f7e54e`) raised
  **P1-1**: future `vintage` / consensus `observation_date` / curve `date` were not checked
  against the decision cutoff. Code `360b161` adds exactly those guards in
  `goe/evidence/external.py:61-70,124-134`, plus tests
  `tests/test_external_evidence.py::test_future_vintage_observation_and_curve_date_rejected`.
  The prior P2 reopen path `archived -> active` is also closed in `goe/db.py` (archived is now
  terminal for status updates). Focused read-only run: 18 passed in
  `tests/test_external_evidence.py tests/test_research_quality.py tests/test_research_v2.py`.
- **No new P0. No new P1 found** in the research gate / candidates / A→B state.
- P2 (documentation/process, non-blocking):
  1. `QA_IDENTITY_FINAL.md` (committed at `360b161`) still states **HOLD / P1** because it
     reviewed `9f7e54e`; it is stale relative to the fix in the same commit. There is no
     separate post-fix independent-QA artifact beyond the 231-test release proof.
  2. `QA_RESEARCH_FINAL2.md` also reviewed code `9f7e54e`; its PASS should not be cited as
     post-`360b161` verification.
  3. `PROJECT_STATE.md` mixes 231/232 test counts; `exports/research_candidates_2026-11-13.json`
     is an old export (official artifact is `evaluation/v2_candidates_20_2026-11-13.json`).
  4. `data/policy_curve.csv` still uses the old schema; consensus/OIS are `enabled: false`,
     so this is dormant, but enabling with old files would return `None` (missing columns).

## 6. Allowed conclusion
**RESEARCH GATE: PASS (P2 only) — no new P0/P1.**  
20 candidates / 0 research / 4 watch / 16 archive / 0 eligible; N225 high/partial/watch;
contract 20/20; A→B correctly blocked (0 task); quality audit descriptive only.  
**DISCOVERY VALUE: NOT VALIDATED** — do not claim discovery, alpha, mispricing, or validated
consensus/OIS evidence.
