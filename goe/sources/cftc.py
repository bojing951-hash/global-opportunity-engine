"""CFTC Commitments of Traders adapter (official, weekly).

Public history ZIPs, one file per calendar year (verified 2026-11-13)::

    https://www.cftc.gov/files/dea/history/fut_fin_txt_{YEAR}.zip      (TFF)
    https://www.cftc.gov/files/dea/history/fut_disagg_txt_{YEAR}.zip   (Disagg)

``fut_fin_txt`` is the **Traders in Financial Futures** report, not the legacy
non-commercial report, so the metric mapping is explicit:

* ``report=fin``   + ``net_asset_manager``  -> Asset_Mgr long - short
* ``report=fin``   + ``net_lev_money``      -> Lev_Money long - short
* ``report=disagg``+ ``net_managed_money``  -> M_Money long - short

Open interest (``Open_Interest_All``) is emitted as ``<id>:oi``.

Market-name drift (observed while scanning 2015-2026): CFTC renamed six of the
configured markets in the 2022 files. Exact names from config are matched
first; for the years before the rename a documented historical alias is used
and reported in a note. No other fuzzy matching is done.

Report dates are Tuesdays (``Report_Date_as_YYYY-MM-DD``); publication is
Friday ~15:30 ET. The report date, not the publication date, is stored.
"""

from __future__ import annotations

import io
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from .. import project_root
from .base import FetchNote, FetchResult, IndicatorProvider, ProviderError, normalize_indicators
from .http import shared_client

CACHE_DIR = "cftc"
URL = "https://www.cftc.gov/files/dea/history/{prefix}_{year}.zip"
PREFIX = {"fin": "fut_fin_txt", "disagg": "fut_disagg_txt"}

METRIC_COLUMNS = {
    ("fin", "net_asset_manager"): ("Asset_Mgr_Positions_Long_All", "Asset_Mgr_Positions_Short_All"),
    ("fin", "net_lev_money"): ("Lev_Money_Positions_Long_All", "Lev_Money_Positions_Short_All"),
    ("disagg", "net_managed_money"): ("M_Money_Positions_Long_All", "M_Money_Positions_Short_All"),
}

# Canonical (2022+) market name -> historical names used by older CFTC files.
# Verified by scanning every fut_fin/fut_disagg file from 2015 to 2026.
MARKET_ALIASES = {
    "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE": (
        "E-MINI S&P 500 STOCK INDEX - CHICAGO MERCANTILE EXCHANGE",
    ),
    "UST 10Y NOTE - CHICAGO BOARD OF TRADE": (
        "10-YEAR U.S. TREASURY NOTES - CHICAGO BOARD OF TRADE",
    ),
    "USD INDEX - ICE FUTURES U.S.": (
        "U.S. DOLLAR INDEX - ICE FUTURES U.S.",
    ),
    "WTI-PHYSICAL - NEW YORK MERCANTILE EXCHANGE": (
        "CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE",
    ),
    "NAT GAS NYME - NEW YORK MERCANTILE EXCHANGE": (
        "NATURAL GAS - NEW YORK MERCANTILE EXCHANGE",
    ),
    "COPPER- #1 - COMMODITY EXCHANGE INC.": (
        "COPPER-GRADE #1 - COMMODITY EXCHANGE INC.",
    ),
    # config/positioning.yaml contains the unquoted YAML scalar
    # ``COPPER- #1 - COMMODITY EXCHANGE INC.``; YAML treats " #" as a comment,
    # so the config value actually parsed is "COPPER-". Resolve both spellings.
    "COPPER-": (
        "COPPER- #1 - COMMODITY EXCHANGE INC.",
        "COPPER-GRADE #1 - COMMODITY EXCHANGE INC.",
    ),
}

DATE_CANDIDATES = ("Report_Date_as_YYYY-MM-DD", "As_of_Date_In_Form_YYMMDD")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cache_path(name: str) -> Path:
    path = project_root() / "data" / "cache" / CACHE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path / name


def decode_cftc_bytes(body: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            continue
    return body.decode("latin-1", errors="replace")


def match_market(names: set[str], market: str) -> tuple[str | None, bool]:
    """Return ``(matched_name, used_alias)`` for a configured market string."""
    if market in names:
        return market, False
    for alias in MARKET_ALIASES.get(market, ()):
        if alias in names:
            return alias, True
    return None, False


def extract_positions(
    df: pd.DataFrame, spec: dict[str, Any]
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Extract net position + open interest for one spec from a CFTC year frame."""
    info: dict[str, Any] = {"matched_market": None, "used_alias": False, "rows": 0}
    report = str(spec.get("report") or "")
    metric = str(spec.get("metric") or "")
    key = (report, metric)
    if key not in METRIC_COLUMNS:
        raise ValueError(f"unsupported CFTC report/metric combination: {report}/{metric}")
    if "Market_and_Exchange_Names" not in df.columns:
        raise ValueError("CFTC frame lacks Market_and_Exchange_Names")
    date_column = next((c for c in DATE_CANDIDATES if c in df.columns), None)
    if date_column is None:
        raise ValueError("CFTC frame has no report date column")

    long_col, short_col = METRIC_COLUMNS[key]
    for column in (long_col, short_col):
        if column not in df.columns:
            raise ValueError(f"CFTC {report} frame lacks column {column}")

    canonical = str(spec.get("market") or "")
    names = set(df["Market_and_Exchange_Names"].dropna().astype(str))
    # A single yearly CFTC file can contain the market under its old *and* new
    # name (the 2022 rename happened mid-year), so concatenate every matching
    # spelling instead of choosing one. Exact/canonical spelling wins on ties.
    matched_names: list[str] = []
    if canonical in names:
        matched_names.append(canonical)
    for alias in MARKET_ALIASES.get(canonical, ()):
        if alias in names:
            matched_names.append(alias)
    if not matched_names:
        info["missing_market"] = True
        return pd.DataFrame(columns=["date", "series_id", "value", "unit"]), info
    info["matched_market"] = matched_names[0]
    info["matched_markets"] = matched_names
    info["used_alias"] = any(name != canonical for name in matched_names)

    part = df[df["Market_and_Exchange_Names"].astype(str).isin(matched_names)].copy()
    part["date"] = pd.to_datetime(part[date_column], errors="coerce")
    part = part.dropna(subset=["date"])
    part["_name_priority"] = (part["Market_and_Exchange_Names"].astype(str) != canonical).astype(int)
    part = part.sort_values(["date", "_name_priority"]).drop_duplicates(subset=["date"], keep="first")
    longs = pd.to_numeric(part[long_col], errors="coerce")
    shorts = pd.to_numeric(part[short_col], errors="coerce")
    net = longs - shorts
    oi = pd.to_numeric(part.get("Open_Interest_All"), errors="coerce") \
        if "Open_Interest_All" in part.columns else pd.Series(float("nan"), index=part.index)

    rows: list[pd.DataFrame] = []
    net_part = pd.DataFrame({"date": part["date"], "value": net}).dropna(subset=["value"])
    if not net_part.empty:
        net_part["series_id"] = spec["id"]
        net_part["unit"] = str(spec.get("unit") or "contracts")
        rows.append(net_part)
    oi_part = pd.DataFrame({"date": part["date"], "value": oi}).dropna(subset=["value"])
    if not oi_part.empty:
        oi_part["series_id"] = f"{spec['id']}:oi"
        oi_part["unit"] = str(spec.get("unit") or "contracts")
        rows.append(oi_part)
    if not rows:
        return pd.DataFrame(columns=["date", "series_id", "value", "unit"]), info
    out = pd.concat(rows, ignore_index=True)
    out = out.drop_duplicates(subset=["series_id", "date"], keep="last")
    info["rows"] = len(out)
    return out, info


class CftcProvider(IndicatorProvider):
    provider_id = "cftc"

    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    @property
    def client(self) -> Any:
        return self._client or shared_client()

    def fetch_indicators(
        self, specs: Sequence[dict[str, Any]], start: str | None = None
    ) -> FetchResult:
        t0 = time.monotonic()
        fetched_at = _utc_now()
        notes: list[FetchNote] = []
        errors: list[str] = []
        frames: list[pd.DataFrame] = []

        positioning = [s for s in specs if s.get("kind") == "positioning"]
        for spec in specs:
            if spec.get("kind") != "positioning":
                notes.append(FetchNote("unsupported_spec", "warning",
                                       f"cftc ignores kind={spec.get('kind')}", spec.get("id", "")))
        if not positioning:
            raise ProviderError("cftc: no positioning specs supplied")

        current_year = datetime.now(timezone.utc).year
        start_year = int(str(start)[:4]) if start else 2015
        start_year = max(2010, start_year)
        if start:
            earliest = pd.Timestamp(start)
        else:
            earliest = pd.Timestamp(f"{start_year}-01-01")

        by_report: dict[str, list[dict[str, Any]]] = {}
        for spec in positioning:
            report = str(spec.get("report") or "")
            if report not in PREFIX:
                errors.append(f"CFTC {spec['id']}: unknown report {report!r}")
                notes.append(FetchNote("bad_spec", "error",
                                       f"CFTC {spec['id']}: unknown report {report!r}", spec["id"]))
                continue
            by_report.setdefault(report, []).append(spec)

        coverage: dict[str, list[int]] = {str(s["id"]): [] for s in positioning}
        alias_years: dict[str, list[int]] = {}
        alias_names: dict[str, set[str]] = {}
        for report, report_specs in by_report.items():
            for year in range(start_year, current_year + 1):
                df = self._load_year(report, year, current_year, notes, errors)
                if df is None:
                    continue
                for spec in report_specs:
                    try:
                        part, info = extract_positions(df, spec)
                    except Exception as exc:  # noqa: BLE001 - one bad spec must not kill the rest
                        errors.append(f"CFTC {spec['id']} {year}: {type(exc).__name__}: {exc}")
                        notes.append(FetchNote("parse_failed", "error",
                                               f"CFTC {spec['id']} {year} parse failed: {exc}",
                                               spec["id"]))
                        continue
                    if part.empty:
                        continue
                    coverage[str(spec["id"])].append(year)
                    if info.get("used_alias"):
                        alias_years.setdefault(str(spec["id"]), []).append(year)
                        canonical = str(spec.get("market") or "")
                        for name in info.get("matched_markets") or []:
                            if str(name) != canonical:
                                alias_names.setdefault(str(spec["id"]), set()).add(str(name))
                    frames.append(part[["series_id", "date", "value", "unit"]])

        # ------------------------------------------------------------ provenance
        for spec in positioning:
            sid = str(spec["id"])
            years = coverage.get(sid) or []
            if alias_years.get(sid):
                names = sorted(alias_names.get(sid, set()))
                notes.append(FetchNote(
                    "market_alias", "info",
                    f"{sid}: matched alternate CFTC market name(s) {names} for years "
                    f"{min(alias_years[sid])}-{max(alias_years[sid])} (CFTC renamed markets in 2022)",
                    sid,
                ))
            if str(spec.get("market") or "").strip() == "COPPER-":
                notes.append(FetchNote(
                    "config_market_truncated", "warning",
                    "POS_COPPER_MM: config market 'COPPER- #1 - COMMODITY EXCHANGE INC.' is an "
                    "unquoted YAML scalar; ' #' starts a comment so the parsed value is 'COPPER-'. "
                    "Resolved via a documented alias; quote the config value to fix at source.",
                    sid,
                ))
            if not years:
                notes.append(FetchNote("series_missing", "warning",
                                       f"{sid}: market not found in any fetched CFTC year", sid))
            elif years and min(years) > start_year:
                notes.append(FetchNote("partial_coverage", "info",
                                       f"{sid}: first matched CFTC year is {min(years)} "
                                       f"(requested from {start_year})", sid))

        frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
            columns=["series_id", "date", "value", "unit"]
        )
        fetched_any = not frame.empty
        if not frame.empty:
            frame = frame[frame["date"] >= earliest]
            frame = frame[frame["value"].notna()]
            oi_mask = frame["series_id"].astype(str).str.endswith(":oi")
            bad_oi = oi_mask & (frame["value"] < 0)
            n_bad = int(bad_oi.sum())
            if n_bad:
                notes.append(FetchNote("validation_dropped", "warning",
                                       f"cftc dropped {n_bad} negative open-interest rows", "cftc"))
                frame = frame[~bad_oi]
        if frame.empty:
            if fetched_any:
                notes.append(FetchNote("no_new_observations", "info",
                                       f"cftc: source data ends before requested start {start}", "cftc"))
                return FetchResult(frame=normalize_indicators(pd.DataFrame(), self.provider_id, fetched_at),
                                   source_id=self.provider_id, fetched_at=fetched_at,
                                   notes=notes, errors=errors, elapsed_s=time.monotonic() - t0)
            raise ProviderError(f"{self.provider_id}: no CFTC rows fetched ({'; '.join(errors[:3])})")
        frame = normalize_indicators(frame, self.provider_id, fetched_at)
        return FetchResult(frame=frame, source_id=self.provider_id, fetched_at=fetched_at,
                           notes=notes, errors=errors, elapsed_s=time.monotonic() - t0)

    # ------------------------------------------------------------------ cache
    def _load_year(
        self,
        report: str,
        year: int,
        current_year: int,
        notes: list[FetchNote],
        errors: list[str],
    ) -> pd.DataFrame | None:
        path = _cache_path(f"{PREFIX[report]}_{year}.zip")
        if year < current_year and path.exists() and path.stat().st_size > 0:
            try:
                return self._read_zip(path.read_bytes())
            except Exception as exc:  # noqa: BLE001 - corrupt cache, refetch
                notes.append(FetchNote("cache_unreadable", "warning",
                                       f"CFTC cache {path.name} unreadable ({exc}); refetching", report))
        try:
            body = self.client.get(URL.format(prefix=PREFIX[report], year=year)).content
            path.write_bytes(body)
            return self._read_zip(body)
        except Exception as exc:  # noqa: BLE001 - provider boundary
            if path.exists() and path.stat().st_size > 0:
                notes.append(FetchNote("cache_fallback", "warning",
                                       f"CFTC {report} {year} download failed ({exc}); using cached zip",
                                       report))
                try:
                    return self._read_zip(path.read_bytes())
                except Exception:  # noqa: BLE001
                    pass
            errors.append(f"CFTC {report} {year}: {type(exc).__name__}: {exc}")
            notes.append(FetchNote("year_failed", "error",
                                   f"CFTC {report} {year} download failed: {exc}", str(year)))
            return None

    @staticmethod
    def _read_zip(body: bytes) -> pd.DataFrame:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            members = [m for m in archive.namelist() if not m.endswith("/")]
            if not members:
                raise ValueError("CFTC zip is empty")
            text = decode_cftc_bytes(archive.read(members[0]))
        frame = pd.read_csv(io.StringIO(text), low_memory=False)
        if "Market_and_Exchange_Names" not in frame.columns:
            raise ValueError("CFTC file has no Market_and_Exchange_Names column")
        return frame
