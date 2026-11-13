"""BIS statistics API adapter (official; policy rates, long CPI, credit).

Endpoint (verified 2026-11-13)::

    https://stats.bis.org/api/v1/data/{FLOW}/{KEY}?format=csv&startPeriod=...

``spec["series"]`` is ``"<FLOW>/<KEY>"`` (e.g. ``WS_CBPOL/M.US``,
``WS_LONG_CPI/M.JP``, ``WS_TC/Q.US.P.A.M``). The returned CSV is **long and
heterogeneous**: one flow/key can contain several unit variants per period.
Observed 2026-11-13:

* ``WS_CBPOL``       one row per month, ``UNIT_MEASURE=368`` (percent).
* ``WS_LONG_CPI``    two rows per month: ``628`` (index, 2015=100) and ``771``
  (percent yoy). The spec's expected unit selects the variant.
* ``WS_TC``          four rows per quarter: domestic-currency (``UNIT_TYPE=XDC``)
  unadjusted and adjusted, a USD conversion, and ``UNIT_MEASURE=367``
  (percent of GDP). ``UNIT_MULT=9`` means the published values are in
  **billions** of the domestic currency, while config labels them ``*_mn``;
  values are stored exactly as published and the mismatch is reported as a
  warning note (never rescaled silently).

Periods are converted to observation dates: ``YYYY-MM`` -> ``YYYY-MM-01``,
``YYYY-Qn`` -> quarter-end month day 1, ``YYYY`` -> ``YYYY-12-01``.
"""

from __future__ import annotations

import io
import re
import time
from datetime import datetime, timezone
from typing import Any, Sequence

import pandas as pd

from .base import FetchNote, FetchResult, IndicatorProvider, ProviderError, normalize_indicators
from .http import shared_client

BASE_URL = "https://stats.bis.org/api/v1/data/{flow}/{key}?format=csv&startPeriod={start}"
UNIT_BY_MEASURE = {"628": "index", "771": "percent_yoy", "368": "percent", "367": "percent", "770": "percent"}
_QUARTER_RE = re.compile(r"^(\d{4})-Q([1-4])$")
_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")
_YEAR_RE = re.compile(r"^(\d{4})$")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def period_to_date(period: str) -> pd.Timestamp | None:
    """Convert a BIS TIME_PERIOD string to the stored observation date."""
    text = str(period).strip()
    match = _QUARTER_RE.match(text)
    if match:
        return pd.Timestamp(year=int(match.group(1)), month=int(match.group(2)) * 3, day=1)
    match = _MONTH_RE.match(text)
    if match:
        return pd.Timestamp(year=int(match.group(1)), month=int(match.group(2)), day=1)
    match = _YEAR_RE.match(text)
    if match:
        return pd.Timestamp(year=int(match.group(1)), month=12, day=1)
    try:
        return pd.Timestamp(text)
    except (ValueError, TypeError):
        return None


def _select_variant(df: pd.DataFrame, spec: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Pick the row variant that matches the spec's expected unit.

    Returns ``(selected_frame, meta)`` where meta carries the observed unit
    measure/multiplier so the provider can note conflicts.
    """
    flow = str(spec.get("series", "")).split("/", 1)[0]
    spec_unit = str(spec.get("unit") or "")
    meta: dict[str, Any] = {"flow": flow, "spec_unit": spec_unit}
    selected = df.copy()

    if "UNIT_MEASURE" in selected.columns:
        selected["UNIT_MEASURE"] = selected["UNIT_MEASURE"].astype(str)

    if flow.startswith("WS_TC"):
        if "UNIT_TYPE" in selected.columns and (selected["UNIT_TYPE"] == "XDC").any():
            selected = selected[selected["UNIT_TYPE"] == "XDC"]
        if "TC_ADJUST" in selected.columns and (selected["TC_ADJUST"] == "U").any():
            selected = selected[selected["TC_ADJUST"] == "U"]
        meta["unit"] = spec_unit
        if "UNIT_MEASURE" in selected.columns and not selected.empty:
            meta["unit_measure"] = str(selected["UNIT_MEASURE"].iloc[0])
        if "UNIT_MULT" in selected.columns and not selected.empty:
            meta["unit_mult"] = str(selected["UNIT_MULT"].iloc[0])
    elif flow.startswith("WS_LONG_CPI"):
        expected = "628" if spec_unit == "index" else "771" if spec_unit.startswith("percent") else None
        meta["expected_measure"] = expected
        if expected and "UNIT_MEASURE" in selected.columns and expected in set(selected["UNIT_MEASURE"]):
            selected = selected[selected["UNIT_MEASURE"] == expected]
        if "UNIT_MEASURE" in selected.columns and not selected.empty:
            observed = str(selected["UNIT_MEASURE"].iloc[0])
            meta["unit_measure"] = observed
            meta["unit"] = UNIT_BY_MEASURE.get(observed, spec_unit)
        else:
            meta["unit"] = spec_unit
    elif flow.startswith("WS_CBPOL"):
        meta["unit"] = "percent"
        if "UNIT_MEASURE" in selected.columns and not selected.empty:
            meta["unit_measure"] = str(selected["UNIT_MEASURE"].iloc[0])
    else:
        # Unknown flow: prefer a variant matching the spec unit, then fall back.
        if "UNIT_MEASURE" in selected.columns:
            observed = set(selected["UNIT_MEASURE"])
            matching = [m for m in observed if UNIT_BY_MEASURE.get(m) == spec_unit]
            if matching:
                selected = selected[selected["UNIT_MEASURE"] == matching[0]]
            if not selected.empty:
                meta["unit_measure"] = str(selected["UNIT_MEASURE"].iloc[0])
                meta["unit"] = UNIT_BY_MEASURE.get(meta["unit_measure"], spec_unit)
            else:
                meta["unit"] = spec_unit
        else:
            meta["unit"] = spec_unit
    return selected, meta


def parse_bis_csv(text: str, spec: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Parse a BIS CSV response for one spec into ``date, value, unit`` rows."""
    if not text or not text.strip():
        return pd.DataFrame(columns=["date", "value", "unit"]), {"flow": spec.get("series", "")}
    raw = pd.read_csv(io.StringIO(text))
    if "TIME_PERIOD" not in raw.columns or "OBS_VALUE" not in raw.columns:
        raise ValueError("BIS CSV lacks TIME_PERIOD/OBS_VALUE columns")
    raw["OBS_VALUE"] = pd.to_numeric(raw["OBS_VALUE"], errors="coerce")
    raw = raw.dropna(subset=["OBS_VALUE"])
    selected, meta = _select_variant(raw, spec)
    if selected.empty:
        return pd.DataFrame(columns=["date", "value", "unit"]), meta
    selected = selected.copy()
    selected["date"] = selected["TIME_PERIOD"].map(period_to_date)
    selected = selected.dropna(subset=["date"])
    selected = selected.drop_duplicates(subset=["date"], keep="first")
    selected["value"] = pd.to_numeric(selected["OBS_VALUE"], errors="coerce")
    selected["unit"] = meta.get("unit") or str(spec.get("unit") or "")
    selected = selected.dropna(subset=["value"]).sort_values("date")
    return selected[["date", "value", "unit"]].reset_index(drop=True), meta


class BisProvider(IndicatorProvider):
    provider_id = "bis"

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
        fetched_any = False

        for spec in specs:
            if spec.get("kind") != "macro" or not spec.get("series"):
                notes.append(FetchNote("unsupported_spec", "warning",
                                       f"bis ignores spec {spec.get('id')}", spec.get("id", "")))
                continue
            flow, _, key = str(spec["series"]).partition("/")
            if not key:
                errors.append(f"BIS {spec['id']}: series must be '<FLOW>/<KEY>', got {spec['series']!r}")
                notes.append(FetchNote("bad_spec", "error",
                                       f"BIS {spec['id']}: bad series encoding {spec['series']!r}", spec["id"]))
                continue
            frequency = str(spec.get("frequency") or "monthly")
            start_period = self._start_period(start, frequency)
            url = BASE_URL.format(flow=flow, key=key, start=start_period)
            try:
                text = self.client.get(url).content.decode("utf-8-sig", errors="replace")
                parsed, meta = parse_bis_csv(text, spec)
            except Exception as exc:  # noqa: BLE001 - provider boundary
                errors.append(f"BIS {spec['series']}: {type(exc).__name__}: {exc}")
                notes.append(FetchNote("series_failed", "error",
                                       f"BIS {spec['series']} request/parse failed: {exc}", spec["id"]))
                continue
            if parsed.empty:
                notes.append(FetchNote("series_empty", "warning",
                                       f"BIS {spec['series']}: no usable observations", spec["id"]))
                continue
            self._note_units(spec, meta, notes)
            fetched_any = True
            if start:
                parsed = parsed[parsed["date"] >= pd.Timestamp(start)]
            if parsed.empty:
                continue
            parsed = parsed.copy()
            parsed["series_id"] = spec["id"]
            frames.append(parsed[["series_id", "date", "value", "unit"]])

        frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
            columns=["series_id", "date", "value", "unit"]
        )
        if not frame.empty:
            keep = frame["value"].notna()
            unit = frame["unit"].fillna("").astype(str)
            keep &= ~unit.eq("index") | (frame["value"] > 0)
            keep &= ~unit.isin(["USD_mn", "CNY_mn", "USD_bn", "CNY_bn"]) | (frame["value"] > 0)
            keep &= ~unit.eq("percent") | frame["value"].between(-5, 30)
            n_bad = int((~keep).sum())
            if n_bad:
                notes.append(FetchNote("validation_dropped", "warning",
                                       f"bis dropped {n_bad} rows failing unit/range checks", "bis"))
                frame = frame[keep]
        if frame.empty:
            if fetched_any:
                notes.append(FetchNote("no_new_observations", "info",
                                       f"bis: source data ends before requested start {start}", "bis"))
                return FetchResult(frame=normalize_indicators(pd.DataFrame(), self.provider_id, fetched_at),
                                   source_id=self.provider_id, fetched_at=fetched_at,
                                   notes=notes, errors=errors, elapsed_s=time.monotonic() - t0)
            raise ProviderError(f"{self.provider_id}: no BIS rows fetched ({'; '.join(errors[:3])})")
        frame = normalize_indicators(frame, self.provider_id, fetched_at)
        return FetchResult(frame=frame, source_id=self.provider_id, fetched_at=fetched_at,
                           notes=notes, errors=errors, elapsed_s=time.monotonic() - t0)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _start_period(start: str | None, frequency: str) -> str:
        if start:
            ts = pd.Timestamp(start)
        else:
            ts = pd.Timestamp("2015-01-01")
        freq = frequency.lower()
        if freq.startswith("quarter"):
            quarter = (ts.month - 1) // 3 + 1
            return f"{ts.year}-Q{quarter}"
        if freq.startswith("month"):
            return f"{ts.year:04d}-{ts.month:02d}"
        if freq.startswith("annual") or freq.startswith("year"):
            return f"{ts.year}"
        return ts.date().isoformat()

    @staticmethod
    def _note_units(spec: dict[str, Any], meta: dict[str, Any], notes: list[FetchNote]) -> None:
        flow = str(meta.get("flow") or "")
        observed = meta.get("unit_measure")
        if flow.startswith("WS_LONG_CPI"):
            unit = meta.get("unit")
            if unit and unit != str(spec.get("unit")):
                notes.append(FetchNote(
                    "unit_measure_mapped", "info",
                    f"{spec['id']}: source UNIT_MEASURE={observed} -> stored unit {unit!r} "
                    f"(config unit {spec.get('unit')!r})",
                    spec["id"],
                ))
        if flow.startswith("WS_TC") and meta.get("unit_mult") == "9":
            notes.append(FetchNote(
                "unit_mult_conflict", "warning",
                f"{spec['id']}: BIS publishes {meta.get('unit_measure')} values with UNIT_MULT=9 "
                f"(billions) but config unit is {spec.get('unit')!r}; value stored as published, "
                f"not rescaled",
                spec["id"],
            ))
