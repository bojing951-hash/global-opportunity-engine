"""Stable Research Identity Contract.

Identity is derived from business content, never list position:

    as_of + instrument + phenomenon signature

where the phenomenon signature includes detector, direction and window. Reordering
the candidate list, re-running the same scan, or updating hypotheses cannot change
the id. A different asset or a different anomaly gets a different id.
"""
from __future__ import annotations

import hashlib
import re


def phenomenon_fingerprint(*, as_of: str, instrument_id: str, detector: str,
                           direction: str, window: str = "") -> str:
    raw = "|".join([str(as_of), str(instrument_id), str(detector),
                    str(direction), str(window)])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def research_theme_id(*, instrument_id: str, detector: str,
                      direction: str, window: str = "") -> str:
    """Long-lived topic identity: same phenomenon across scan dates."""
    raw = "|".join([str(instrument_id), str(detector), str(direction), str(window)])
    return "RT-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def research_id(*, as_of: str, instrument_id: str, detector: str,
                direction: str, window: str = "") -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(instrument_id))[:48]
    fp = phenomenon_fingerprint(as_of=as_of, instrument_id=instrument_id,
                                detector=detector, direction=direction, window=window)
    return f"RC-{str(as_of).replace('-', '')}-{safe}-{fp}"
