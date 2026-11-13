"""Provider registry.

Indicator providers are registered here. Each provider is optional at import
time: a missing third-party dependency degrades to "provider unavailable"
(recorded as a quality issue by the ingestor) instead of crashing the engine.
"""

from __future__ import annotations

from .base import IndicatorProvider

_MODULES = [
    ("treasury_us", "goe.sources.treasury", "TreasuryUSProvider"),
    ("mof_japan", "goe.sources.mof_japan", "MofJapanProvider"),
    ("ecb", "goe.sources.ecb", "EcbProvider"),
    ("bls", "goe.sources.bls", "BlsProvider"),
    ("bis", "goe.sources.bis", "BisProvider"),
    ("eurostat", "goe.sources.eurostat", "EurostatProvider"),
    ("cftc", "goe.sources.cftc", "CftcProvider"),
    ("akshare_cn_bond", "goe.sources.akshare_cn_bond", "AkshareCnBondProvider"),
    ("shiller", "goe.sources.shiller", "ShillerProvider"),
]


def build_indicator_providers() -> dict[str, IndicatorProvider]:
    import importlib
    import logging

    out: dict[str, IndicatorProvider] = {}
    for pid, module, cls in _MODULES:
        try:
            mod = importlib.import_module(module)
            out[pid] = getattr(mod, cls)()
        except Exception as exc:  # noqa: BLE001 - optional provider
            logging.getLogger(__name__).warning("indicator provider %s unavailable: %s", pid, exc)
    return out
