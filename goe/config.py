"""Typed configuration loading.

All config files live in ``config/`` and are versioned. Nothing here is tuned
on future returns: importance weights are anchored on market size / turnover and
documented in docs/SCORING.md, thresholds are stated apriori and validated by
the historical replay (see docs/VALIDATION.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from . import CONFIG_DIR, project_root

ASSET_CLASSES = {
    "equity_index",
    "equity_etf",
    "sector_equity",
    "fixed_income",
    "credit",
    "fx",
    "commodity",
    "crypto",
    "volatility",
}

REGIONS = {"US", "CN", "HK", "JP", "EA", "UK", "DE", "FR", "IT", "ES", "CH", "KR", "TW", "IN", "BR", "CA", "AU", "MX", "TR", "WORLD"}

LIQUIDITY_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3, "very_high": 4}


class ConfigError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"missing config file: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"config root must be a mapping: {path}")
    return data


def config_path(name: str) -> Path:
    p = Path(name)
    return p if p.is_absolute() else CONFIG_DIR / p


@dataclass(frozen=True)
class Instrument:
    id: str
    name: str
    asset_class: str
    region: str
    currency: str
    source: str
    symbol: str
    importance: float = 0.3
    liquidity: str = "medium"
    role: str = ""
    benchmark: str | None = None
    notes: str = ""

    @property
    def is_equity(self) -> bool:
        return self.asset_class in {"equity_index", "equity_etf", "sector_equity"}

    @property
    def is_risky(self) -> bool:
        return self.asset_class in {"equity_index", "equity_etf", "sector_equity", "credit", "crypto"}


@dataclass(frozen=True)
class CurveDef:
    id: str
    name: str
    provider: str
    currency: str
    region: str
    tenors: tuple[str, ...]
    benchmark_tenors: tuple[str, ...]
    start_year: int
    tier: str = "official"
    notes: str = ""


@dataclass(frozen=True)
class MacroSeries:
    id: str
    name: str
    provider: str
    series: str
    unit: str
    region: str
    frequency: str
    transform: str = "level"
    transform_lags: int = 12
    tier: str = "official"
    importance: float = 0.4
    notes: str = ""


@dataclass(frozen=True)
class PositioningSeries:
    id: str
    name: str
    provider: str
    report: str          # fin | disagg
    market: str          # exact market name in the CFTC file
    metric: str          # net_noncommercial | net_managed_money
    unit: str = "contracts"
    importance: float = 0.4
    maps_to: str | None = None


@dataclass
class Universe:
    instruments: dict[str, Instrument]
    benchmarks: dict[str, str] = field(default_factory=dict)

    def resolve_benchmark(self, inst: Instrument) -> str | None:
        bench = inst.benchmark or self.benchmarks.get(inst.region)
        if bench == inst.id:
            return None
        return bench

    def by_asset_class(self, *classes: str) -> list[Instrument]:
        return [i for i in self.instruments.values() if i.asset_class in classes]

    def of_region(self, *regions: str) -> list[Instrument]:
        return [i for i in self.instruments.values() if i.region in regions]


def _validate_instrument(iid: str, raw: dict[str, Any]) -> Instrument:
    missing = [k for k in ("name", "asset_class", "region", "currency", "source", "symbol") if not raw.get(k)]
    if missing:
        raise ConfigError(f"instrument {iid} missing fields: {missing}")
    if raw["asset_class"] not in ASSET_CLASSES:
        raise ConfigError(f"instrument {iid}: unknown asset_class {raw['asset_class']}")
    if raw["region"] not in REGIONS:
        raise ConfigError(f"instrument {iid}: unknown region {raw['region']}")
    if raw.get("liquidity", "medium") not in LIQUIDITY_RANK:
        raise ConfigError(f"instrument {iid}: unknown liquidity {raw['liquidity']}")
    imp = float(raw.get("importance", 0.3))
    if not 0.0 <= imp <= 1.0:
        raise ConfigError(f"instrument {iid}: importance must be within [0,1]")
    return Instrument(
        id=iid,
        name=str(raw["name"]),
        asset_class=str(raw["asset_class"]),
        region=str(raw["region"]),
        currency=str(raw["currency"]),
        source=str(raw["source"]),
        symbol=str(raw["symbol"]),
        importance=imp,
        liquidity=str(raw.get("liquidity", "medium")),
        role=str(raw.get("role", "")),
        benchmark=raw.get("benchmark"),
        notes=str(raw.get("notes", "")),
    )


@lru_cache(maxsize=1)
def load_universe(path: str | None = None) -> Universe:
    raw = _load(config_path(path or "universe.yaml"))
    instruments: dict[str, Instrument] = {}
    for iid, spec in (raw.get("instruments") or {}).items():
        instruments[iid] = _validate_instrument(iid, spec)
    for inst in instruments.values():
        if inst.benchmark and inst.benchmark not in instruments:
            raise ConfigError(f"instrument {inst.id}: unknown benchmark {inst.benchmark}")
    benchmarks = dict(raw.get("benchmarks") or {})
    # A region benchmark must exist and be an index/ETF.
    for region, bid in benchmarks.items():
        if bid not in instruments:
            raise ConfigError(f"regional benchmark {region} -> unknown instrument {bid}")
    return Universe(instruments=instruments, benchmarks=benchmarks)


@lru_cache(maxsize=1)
def load_curves(path: str | None = None) -> dict[str, CurveDef]:
    raw = _load(config_path(path or "curves.yaml"))
    out: dict[str, CurveDef] = {}
    for cid, spec in (raw.get("curves") or {}).items():
        out[cid] = CurveDef(
            id=cid,
            name=spec["name"],
            provider=spec["provider"],
            currency=spec["currency"],
            region=spec["region"],
            tenors=tuple(spec["tenors"]),
            benchmark_tenors=tuple(spec.get("benchmark_tenors") or spec["tenors"][:2]),
            start_year=int(spec.get("start_year", 2014)),
            tier=spec.get("tier", "official"),
            notes=spec.get("notes", ""),
        )
    return out


@lru_cache(maxsize=1)
def load_macro(path: str | None = None) -> dict[str, MacroSeries]:
    raw = _load(config_path(path or "macro.yaml"))
    out: dict[str, MacroSeries] = {}
    for sid, spec in (raw.get("series") or {}).items():
        out[sid] = MacroSeries(
            id=sid,
            name=spec["name"],
            provider=spec["provider"],
            series=str(spec["series"]),
            unit=spec.get("unit", ""),
            region=spec.get("region", "WORLD"),
            frequency=spec.get("frequency", "monthly"),
            transform=spec.get("transform", "level"),
            transform_lags=int(spec.get("transform_lags", 12)),
            tier=spec.get("tier", "official"),
            importance=float(spec.get("importance", 0.4)),
            notes=spec.get("notes", ""),
        )
    return out


@lru_cache(maxsize=1)
def load_positioning(path: str | None = None) -> dict[str, PositioningSeries]:
    raw = _load(config_path(path or "positioning.yaml"))
    out: dict[str, PositioningSeries] = {}
    for sid, spec in (raw.get("series") or {}).items():
        out[sid] = PositioningSeries(
            id=sid,
            name=spec["name"],
            provider=spec.get("provider", "cftc"),
            report=spec.get("report", "fin"),
            market=spec["market"],
            metric=spec.get("metric", "net_noncommercial"),
            unit=spec.get("unit", "contracts"),
            importance=float(spec.get("importance", 0.4)),
            maps_to=spec.get("maps_to"),
        )
    return out


@lru_cache(maxsize=1)
@lru_cache(maxsize=1)
def load_themes(path: str | None = None) -> dict[str, str]:
    """Map instrument_id -> theme_id (dedupe key for the opportunity layer)."""
    raw = _load(config_path(path or "themes.yaml"))
    out: dict[str, str] = {}
    for theme, members in (raw.get("themes") or {}).items():
        for iid in members or []:
            out[str(iid)] = str(theme)
    return out


def load_sources(path: str | None = None) -> dict[str, dict[str, Any]]:
    raw = _load(config_path(path or "sources.yaml"))
    return dict(raw.get("sources") or {})


def load_yaml_config(name: str) -> dict[str, Any]:
    """Load an arbitrary config file (scoring, thresholds, mechanisms, events)."""
    return _load(config_path(name))


def data_dir() -> Path:
    d = project_root() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def exports_dir() -> Path:
    d = project_root() / "exports"
    d.mkdir(parents=True, exist_ok=True)
    return d
