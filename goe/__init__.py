"""Global Opportunity Engine (goe).

Upstream opportunity-discovery layer for the existing ``investment-agent``
deep-research system. This package never places orders and never calls a paid
API: it collects public market/statistical data, detects anomalies, evaluates
transmission mechanisms and maintains a research opportunity pipeline.
"""

from __future__ import annotations

import os
import ssl
from pathlib import Path

__version__ = "0.1.0"

# The uv-managed interpreter ships without a system CA bundle on macOS; every
# HTTPS call in this package must verify certificates against certifi instead
# of failing closed (or, worse, being silently disabled).
try:  # pragma: no cover - trivial environment shim
    import certifi

    _CA = certifi.where()
    os.environ.setdefault("SSL_CERT_FILE", _CA)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", _CA)
    ssl._create_default_https_context = lambda *a, **k: ssl.create_default_context(cafile=_CA)  # type: ignore[assignment]
except Exception:  # pragma: no cover
    pass


def project_root() -> Path:
    """Repository root, overridable with GOE_ROOT (used by tests)."""
    env = os.environ.get("GOE_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


ROOT = project_root()
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
EXPORT_DIR = ROOT / "exports"
DOCS_DIR = ROOT / "docs"
