# Data source notes — indicator adapters (Agent 1)

Verification window: **2026-11-13** (Asia/Hong_Kong; `fetched_at` in the test run is
`2026-11-13T13:53Z`). All endpoints were called live from this machine. Nothing
below is inferred from documentation alone: coverage numbers are from the actual
backfill described at the bottom, and each observation in the database carries
`source_id` + `fetched_at` + the source's own observation date.

Scope: the nine keyless public sources wired into `goe/sources/` —
`treasury_us`, `mof_japan`, `ecb`, `bls`, `bis`, `eurostat`, `cftc`,
`akshare_cn_bond`, `shiller`. All providers implement
`IndicatorProvider.fetch_indicators(specs, start)` and return a canonical
`FetchResult` frame (`series_id, date, value, unit`) through
`normalize_indicators`. No provider applies a transform (yoy/diff); ingestion
stores the raw published/derived-by-source value.

## Verified coverage (final backfill, 2026-11-13)

| provider | rows | series | first obs | last obs | example last value | unit | tier |
|---|---:|---:|---|---|---|---|---|
| `treasury_us` | 38,421 | 13 | 2014-01-02 | 2026-11-12 | `UST:10Y` 5.10 | percent | official |
| `mof_japan` | 47,115 | 15 | 2014-01-06 | 2026-11-12 | `JGB:10Y` 2.841 | percent | official |
| `ecb` | 36,113 | 11 | 2014-01-02 | 2026-11-12 | `EAC:10Y` 3.3672459164 | percent | official |
| `akshare_cn_bond` | 16,078 | 5 | 2014-01-02 | 2026-11-13 | `CN:10Y` 1.6123 | percent | aggregator |
| `bls` | 565 | 4 | 2015-01-01 | 2026-10-01 | `US_CPI` 337.511 | index | official |
| `bis` | 1,203 | 10 | 2015-01-01 | 2026-10-01 | `US_POLICY_RATE` 3.875 | percent | official |
| `eurostat` | 132 | 1 | 2015-01-01 | 2025-12-01 | `EA_HICP` 2.0 | percent | official |
| `cftc` | 19,776 | 32 | 2015-01-06 | 2026-11-03 | `POS_GOLD_MM` 103,614 | contracts | official |
| `shiller` | 105 | 1 | 2015-01-01 | 2023-09-01 | `US_CAPE` 30.81096 | ratio | official/academic |
| **total** | **159,508** | **92** | | | | | |

`36` configured targets, `0` failed targets. Backfill wall time **20.0 s** with a warm HTTP cache; the first
run while probing the endpoints (partial cache) took **87 s**;
incremental run: **16.2 s**, 499 rows. Numbers per provider are deliberately not
symmetric: they reflect what the public sources actually publish, not a target
row count.

## Validation policy (and two deliberate deviations)

Every provider checks values before they reach `normalize_indicators`, drops
failures, and records the dropped count in a `FetchNote` (`validation_dropped`).
Nothing is interpolated or forward-filled; a source gap is a gap.

* Curves: US par yields accepted in **[0, 25]** percent. The lower bound is
  inclusive because Treasury published **0.00** bill yields during 2014-2015
  (57 `1M` and 13 `3M` observations); using the suggested strict `0 < v` would
  have silently deleted real observations.
* JGB and euro-area AAA curves are accepted in **[-5, 30]** percent. Both
  officially published **negative yields**: 14,434 JGB observations and 14,588
  ECB observations are below zero in the fetched window (JGB 7Y min -0.423%,
  ECB 3Y min -1.002%). The suggested 0..30 window would have deleted them.
* BLS: index/thousands must be `> 0`; percent series within [-100, 100].
* BIS: index and credit levels `> 0`; percent series within [-5, 30].
* Eurostat: HICP annual rate within [-50, 100].
* Shiller CAPE: `(0, 200)`.
* CFTC: net positions finite (negative is normal); open interest `>= 0`.

## treasury_us — US Treasury par yield curve

* **Endpoint** (one CSV per calendar year):
  `https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{YEAR}/all?type=daily_treasury_yield_curve&field_tdr_date_value={YEAR}&page&_format=csv`
* **Format**: header changes over time. `2 Mo` first appears in 2018, `4 Mo` in
  2023, and `1.5 Month` appears from 2025 (ignored). Dates are `MM/DD/YYYY`,
  values are par yields in percent; tenors below 1Y are bill-equivalent rates.
* **Coverage actually fetched**: 13 tenors, 3,217 daily observations each for
  1M/3M/6M/1Y/2Y/3Y/5Y/7Y/10Y/20Y/30Y; `UST:2M` starts **2018-10-16**
  (2,018 obs) and `UST:4M` starts **2022-10-19** (1,016 obs) — these tenors did
  not exist in the earlier files and were not back-filled. Last: 2026-11-12.
* **Publication lag**: same business day, end-of-day (~16:00 ET). The current
  year file is re-downloaded on every run; earlier years are cached.
* **Known gaps**: par yields, not zero-coupon. No breakevens. The 2014-2015
  0.00 bill yields are retained (see validation note). Unknown columns such as
  `1.5 Month` are ignored, never mapped to a configured tenor.
* **Use**: official primary source.

## mof_japan — Japan MOF JGB interest rates

* **Endpoints**:
  * current month: `https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv`
    (**cp932**, two title rows, current month only, ~1 KB);
  * full history: `.../historical/jgbcme_all.csv` (**UTF-8**, one file,
    1974-09-24 onward, ~13k rows).
* **Format**: wide date × tenor table with `Date,1Y,...,40Y`. The number of
  tenor columns changed over time; `-` means "not listed yet" and is skipped,
  not filled. Both files are merged, current-month rows winning on duplicate
  dates.
* **Coverage actually fetched**: 15 tenors × 3,141 business days =
  47,115 rows, **2014-01-06 .. 2026-11-12**. 14,434 observations are negative
  (real published JGB yields; not dropped).
* **Publication lag**: same business day after market close (JST). The
  current-month file is fetched every run; the 1.2 MB history file is cached
  for 24 h (so a month boundary cannot lose the last days of the prior month).
* **Known gaps**: business-day curve only; no intraday; 1974+ history exists
  upstream but the configured backfill starts in 2014.
* **Use**: official primary source.

## ecb — euro-area AAA central-government yield curve

* **Endpoint** (one SDMX series per tenor):
  `https://data-api.ecb.europa.eu/service/data/YC/B.U2.EUR.4F.G_N_A.SV_C_YM.SR_<TENOR>?format=csvdata&startPeriod=<start>`
  with `SR_3M`, `SR_6M`, `SR_1Y` ... `SR_30Y`.
* **Format**: CSV with `TIME_PERIOD`/`OBS_VALUE`; daily business-day
  observations; no key. The curve is the AAA-rated euro-area
  central-government curve, not a single issuer.
* **Coverage actually fetched**: 11 tenors × 3,283 days =
  36,113 rows, **2014-01-02 .. 2026-11-12**. 14,588 negative observations are
  retained (min -1.002%).
* **Publication lag**: one business day after the observation date.
* **Known gaps**: AAA aggregate only (no country BTP/Bund spread); 404/empty
  for a tenor becomes a warning note, not a crash. Per-tenor CSVs are cached
  for 12 h and an incremental run tops up only the recent tail.
* **Use**: official primary source.

## bls — US Bureau of Labor Statistics, public API v1

* **Endpoint**: `POST https://api.bls.gov/publicAPI/v1/timeseries/data/` with
  `{"seriesid": [...], "startyear": "YYYY", "endyear": "YYYY"}`.
* **Format**: string `value`, `period` `M01`..`M12`; `M13` is the annual average
  and is skipped. Monthly dates stored as `YYYY-MM-01`. v1 limits: **25 series
  and 10 years per request**, unauthenticated daily quota; requests are split
  into ≤10-year windows and cached for 12 h (current window) so reruns do not
  burn quota. `CES0000000001` is already in thousands.
* **Coverage actually fetched**: 565 rows for the four configured series.
  `US_CPI`, `US_CORE_CPI`, `US_UNRATE`: 141 monthly obs, 2015-01-01 ..
  2026-10-01. `US_PAYROLLS`: 142 obs, 2015-01-01 .. 2026-10-01.
* **Publication lag**: CPI mid-month following the reference month; payrolls
  and unemployment on the first Friday.
* **Known gaps**: **2025-10 is absent for CPI / core CPI / unemployment** in
  the BLS response (payrolls has it). It is a real source gap and is stored as
  a gap — no fill. Because of it, the automatic US_CPI YoY cross-check cannot
  compute an exact 12-month change and records
  `cpi_crosscheck_skipped` (it does not substitute a different month). The
  provider logs `api_status` when BLS returns anything other than
  `REQUEST_SUCCEEDED`.
* **Use**: official primary source.

## bis — Bank for International Settlements statistics API

* **Endpoint**: `https://stats.bis.org/api/v1/data/<FLOW>/<KEY>?format=csv&startPeriod=<period>`
  (`WS_CBPOL/M.US`, `WS_LONG_CPI/M.JP`, `WS_TC/Q.US.P.A.M`, ...).
* **Format**: long CSV, **not one series per key**. Verified 2026-11-13:
  * `WS_CBPOL`: one row/month, `UNIT_MEASURE=368` (percent).
  * `WS_LONG_CPI`: **two rows per month** — `628` (index, 2015=100) and `771`
    (percent yoy). The provider selects by the spec unit and stores
    `percent_yoy` for 771 (JP_CPI, UK_CPI) and `index` for 628 (CN_CPI).
  * `WS_TC`: four variants per quarter (domestic-currency XDC unadjusted and
    adjusted, USD conversion, and percent-of-GDP 367). The provider selects
    `UNIT_TYPE=XDC` + `TC_ADJUST=U` and stores the value **exactly as
    published**. `UNIT_MULT=9` means the values are in **billions** of the
    domestic currency while config labels them `USD_mn`/`CNY_mn`; a warning
    `unit_mult_conflict` is logged. Do not compare these levels to a
    per-million series without rescaling; the configured yoy transform is
    scale-invariant.
* **Coverage actually fetched**: 10 series, 1,203 rows, 2015-01-01 ..
  2026-10-01. Details: policy rates 142 monthly obs (2015-01..2026-10) except
  **JP_POLICY_RATE starts 2016-09** because BIS's Japanese series has a real
  gap between 2013-05 and 2016-08; `US_CREDIT`/`CN_CREDIT` 45 quarterly obs
  2015-Q1..2026-Q1; `CN_CPI`/`JP_CPI` 141 obs through 2026-09.
* **Publication lag**: policy rates ~1 month; long CPI ~1 month; total credit
  ~2 quarters (last observation 2026-Q1 observed in 2026-11).
* **Known gaps**: heterogeneous unit variants (handled), JP policy-rate gap,
  credit levels in billions vs `*_mn` label. Quarterly `startPeriod` is floored
  to a quarter (`YYYY-Qn`) because BIS rejects arbitrary dates such as
  `2026-02-19` with HTTP 404.
* **Use**: official primary source.

## eurostat — Eurostat dissemination API (JSON-stat 2.0)

* **Endpoint**:
  `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/prc_hicp_manr?geo=EA&coicop=CP00&unit=RCH_A&format=JSON&lang=EN`
* **Format**: JSON-stat 2.0. The parser implements the general linear-index
  decode using `id` (dimension order), `size`, and each dimension's
  `category.index` map; it is not a time-only shortcut. For the configured
  query only `time` varies; a response where a non-time dimension varies is
  rejected as ambiguous instead of silently collapsing categories.
* **Coverage actually fetched**: `EA_HICP` 132 monthly obs,
  **2015-01-01 .. 2025-12-01**. The response's own `updated` field is
  `2026-02-06T23:00:00+0100`; the mirror served no 2026 months at verification
  time, so 2026 is an empty window (the provider returns an empty result with
  `no_new_observations` rather than raising, because the endpoint did return
  data).
* **Publication lag**: HICP flash at the end of the reference month, final
  release mid-following month; the observed mirror is substantially staler.
* **Known gaps**: euro-area aggregate only; one JSON request per run, no cache.
* **Use**: official primary source.

## cftc — CFTC Commitments of Traders public history

* **Endpoints**:
  `https://www.cftc.gov/files/dea/history/fut_fin_txt_{YEAR}.zip` (TFF) and
  `.../fut_disagg_txt_{YEAR}.zip` (Disaggregated). The ZIP member names are
  `FinFutYY.txt` / `f_year.txt` at verification time; the provider reads the
  first member rather than hard-coding those names.
* **Format**: `fut_fin_txt` is **TFF**, not legacy non-commercial. Metrics:
  `net_asset_manager` = Asset_Mgr long − short; `net_lev_money` = Lev_Money
  long − short; `net_managed_money` = M_Money long − short. Open interest
  (`Open_Interest_All`) is emitted as `<id>:oi`. Report date is
  `Report_Date_as_YYYY-MM-DD` (Tuesday close); the report date, not the Friday
  publication date, is stored.
* **Market-name drift (verified by scanning 2015-2026)**: six configured
  markets were renamed in the **2022** files, and the 2022 file contains the old
  name for January and the new name from February. Matching therefore accepts
  the exact configured name **plus a documented historical alias**, and
  concatenates both spellings within a year:
  * `E-MINI S&P 500` ↔ `E-MINI S&P 500 STOCK INDEX`
  * `UST 10Y NOTE` ↔ `10-YEAR U.S. TREASURY NOTES`
  * `USD INDEX` ↔ `U.S. DOLLAR INDEX`
  * `WTI-PHYSICAL` ↔ `CRUDE OIL, LIGHT SWEET`
  * `NAT GAS NYME` ↔ `NATURAL GAS`
  * `COPPER- #1` ↔ `COPPER-GRADE #1`
* **Coverage actually fetched**: 16 configured markets → 16 net + 16 open
  interest series = 19,776 rows, **2015-01-06 .. 2026-11-03** (618 weekly
  reports per series). The final 2022 renames and the mid-year transition are
  included; without the alias handling, 6 series would have started in 2022 and
  the January 2022 weeks would be missing.
* **Publication lag**: report as of Tuesday close, published **Friday ~15:30
  ET**. The replay layer must apply that lag; ingestion stores the Tuesday
  report date.
* **Known gaps**: weekly; federal-holiday Tuesdays (e.g. 2017-07-04,
  2018-12-25, 2019-01-01, 2023-07-04, 2025-11-11) have no Tuesday-dated row
  because CFTC dates the report to the prior business day — this is a source
  convention, not a missing series. `POS_COPPER_MM` was observed during
  development to parse as `COPPER-` because the YAML scalar was unquoted
  (` #` starts a YAML comment); the config owner has since quoted it. The
  adapter still tolerates the truncated spelling and logs
  `config_market_truncated` if it sees it. Current-year ZIPs are refreshed on
  every run; earlier years are cached.
* **Use**: official primary source.

## akshare_cn_bond — China government bond yields (aggregator)

* **Call**: `akshare.bond_zh_us_yield_em(start_date="20140101")` (lazy import).
  **Akshare 1.20.42 renamed the function**: the documented
  `bond_zh_us_rate` does not exist in this version; `bond_zh_us_yield_em` has
  the same `start_date` argument and columns. The provider prefers the old name
  when present and falls back to the new one.
* **Format**: wide daily table from eastmoney/ChinaBond with columns
  `日期`, `中国国债收益率2年/5年/10年/30年`, US Treasury columns, etc. The
  provider emits `CN:2Y`, `CN:5Y`, `CN:10Y`, `CN:30Y` and the cross-check
  series **`CN:US10Y_CHECK`** from `美国国债收益率10年` (unit percent). The
  cross-check id is intentionally not in `docs/id_reference.md`; it is an
  auxiliary quality series.
* **Coverage actually fetched**: 4 CN tenors × 3,215 days + 3,218 US-check
  observations = 16,078 rows, **2014-01-02 .. 2026-11-13**. The whole table is
  cached as CSV for 12 h; the cache is checked for coverage before reuse, and a
  cache written from a later start is refetched.
* **Publication lag**: daily after the China market close; aggregator adds
  0-1 day.
* **Known gaps**: eastmoney/jin10 are flaky from some networks
  (ProxyError/SSLError/ReadTimeout); all failures become `FetchNote`s with
  severity `error` and an empty frame, never an exception. This is the one
  adapter whose HTTP is performed inside a third-party library rather than
  through `shared_client`. Cross-check against `treasury_us` shows aggregator
  artifacts: akshare carries US 10Y values on **2017-07-04, 2017-09-04 and
  2017-10-09** (US holidays) that the Treasury file does not, and lacks
  Treasury values for **2014-10-03 and 2015-01-02**. Compare only common dates.
* **Use**: aggregator; always flag as such downstream.

## shiller — Yale / Robert Shiller online data

* **Endpoint**: `http://www.econ.yale.edu/~shiller/data/ie_data.xls` (legacy
  BIFF `.xls`; `xlrd` required, installed in the venv).
* **Format**: sheet `Data`, header on row 8 (0-indexed 7):
  `Date, P, D, E, CPI, Date Fraction, Long Interest Rate GS10, Real Price, ...`
  and **CAPE is column 12** at that header row. The parser finds the `Date`
  header and the exact `CAPE` label rather than hard-coding either (there are
  nearby "Excess CAPE Yield"/"TR CAPE" header stacks that must not be
  confused). The last sheet row is a text note and is skipped.
* **Decimal dates**: the fractional part encodes the month; **`2022.1` means
  October**, not January, because float formatting dropped the trailing zero.
  The parser multiplies the fraction by 100 instead of counting digits.
* **Coverage actually fetched**: `US_CAPE` 105 monthly obs,
  **2015-01-01 .. 2023-09-01** (CAPE itself is available from 1881-01 in the
  file; the configured backfill starts 2015). Last value 30.81096 (ratio).
  120 pre-1881 rows have a blank CAPE and are skipped.
* **Publication lag**: monthly; in this environment the public workbook itself
  ends at 2023-09 (1,169 days old at verification), so the provider emits a
  `series_stale` warning. It does not extrapolate.
* **Known gaps**: monthly; S&P 500 aggregate only; last months are often
  partly estimated by the author, and the most recent CAPE can be blank.
* **Use**: official/academic primary source.

## Cross-provider checks and provenance

* `CN:US10Y_CHECK` vs `UST:10Y` is the built-in aggregator check described
  above; the quality layer should treat holiday-date differences as aggregator
  noise, not as Treasury revisions.
* BIS `WS_LONG_CPI` unit mapping is recorded at row level: JP_CPI and UK_CPI
  carry `percent_yoy` (source 771), CN_CPI carries `index` (source 628), even
  though `config/macro.yaml` labels the former as `percent`. The notes
  `unit_measure_mapped` explain the mapping on every run.
* No provider applies `yoy`/`diff`; transforms remain an analysis-time
  concern. No value is carried forward; every row's date is the source's own
  observation date.

## Caching, incremental behaviour, and failure semantics

Cache root: `data/cache/<provider>/` (overridable via `GOE_ROOT`).

| provider | cache policy |
|---|---|
| treasury_us | one file per year; past years reused, **current year always re-downloaded** |
| mof_japan | full history 24 h; current-month file every run |
| ecb | per-tenor CSV 12 h; incremental request tops up only the recent tail |
| bls | per-window JSON 12 h for the current window; past windows reused (quota protection) |
| bis | no cache (responses are small; `startPeriod` does the windowing) |
| eurostat | no cache (one ~18 KB request per run) |
| cftc | one ZIP per report/year; past years reused, **current year always re-downloaded** |
| akshare_cn_bond | wide CSV 12 h; full-history call so the cache always covers 2014+ |
| shiller | workbook 24 h |

A provider that fetched at least one usable observation but whose rows are all
older than a recent `start` returns an empty frame with `no_new_observations`
(not an error). `ProviderError` is raised only when nothing at all could be
fetched. Per-file/per-series failures go to `FetchResult.errors` and a
`FetchNote`; HTTP failures never become fabricated values.

## Reproduce

```bash
cd <repo>

# offline parsing tests (no network)
.venv/bin/python -m pytest tests/test_sources_indicators.py -q -m "not network"

# live smoke test, one per provider (skips if the endpoint is unreachable;
# fails if a reachable endpoint parses to zero rows)
.venv/bin/python -m pytest tests/test_sources_indicators.py -q -m network

# end-to-end backfill into a throwaway database
rm -f data/_agent1_test.db*
.venv/bin/python - <<'PY'
from goe.db import Store
from goe.ingest import Ingestor
s = Store("data/_agent1_test.db"); ing = Ingestor(s)
ing.register_metadata()
print(ing.ingest_indicators(mode="backfill").to_dict())
import pandas as pd
print(pd.read_sql_query(
    "SELECT series_id, COUNT(*) n, MIN(date) f, MAX(date) l FROM indicators "
    "GROUP BY series_id ORDER BY series_id", s.conn).to_string())
PY
rm -f data/_agent1_test.db*
```

Observed result of that exact backfill on 2026-11-13:
`{'rows': 159508, 'targets': 36, 'failed_targets': [], 'n_notes': 18,
'elapsed_s': 20.04}`.

## Interface issues found (not edited — outside this agent's scope)

1. **`goe/sources/http.py` line 84**:
   `self.retry.retry_status | {401, 403, 404}` raises
   `TypeError: unsupported operand type(s) for |: 'tuple' and 'set'` whenever a
   request returns 401/403/404 (or any retryable status that reaches that
   line). The intended behavior was to treat 401/403/404 as non-retryable and
   re-raise `HTTPError`. Because of this, a genuine 404/missing tenor surfaces
   as `TypeError`, making status-based handling impossible from adapter code.
   Suggested fix (not applied): `set(self.retry.retry_status) | {401, 403, 404}`.
2. **BIS unit mismatch in `config/macro.yaml`**: `US_CREDIT`/`CN_CREDIT` are
   labelled `USD_mn`/`CNY_mn`, but `WS_TC` publishes billions
   (`UNIT_MULT=9`). Values are stored as published and the conflict is logged.
   Either relabel the config units as `*_bn` or document the scale explicitly.
3. **`CN:US10Y_CHECK` is not in `docs/id_reference.md` or `series_meta`** (it
   is emitted only for the quality cross-check). If downstream tooling
   enumerates `id_reference`, add it there or keep it explicitly quality-only.
4. **`config/positioning.yaml` YAML scalar**: during development the unquoted
   `COPPER- #1 - ...` parsed as `COPPER-` because ` #` starts a comment. It is
   now quoted in the config; the adapter retains a defensive alias so an
   unquoted value cannot silently zero the series.
5. **`Ingestor._indicator_start` passes one earliest start per provider**, not
   per series. All adapters accept this and window per spec internally, but a
   per-spec start hint would avoid fetching old windows for newly added series.
