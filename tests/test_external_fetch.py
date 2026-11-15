from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "fetch_ext", Path(__file__).resolve().parents[1] / "scripts" / "fetch_external_evidence.py")
fetch_ext = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(fetch_ext)


def test_build_curve_marks_next_day_availability_and_proxy_source():
    rows = fetch_ext.build_curve(
        [("2026-01-02", 4.30)],
        [("2026-01-02", 4.00)],
        [("2026-01-02", 4.50)],
    )
    assert all(r["available_at"] == "2026-01-03" for r in rows)
    assert {r["tenor"] for r in rows} == {"2Y", "10Y", "SOFR"}
    assert all("not term OIS" in r["source"] for r in rows)
