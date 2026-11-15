#!/usr/bin/env python3
"""Fetch a public policy-curve proxy into the external-evidence CSV.

This is NOT a term OIS curve. It fetches FRED's SOFR / 2Y / 10Y Treasury series
as a transparent *policy-path proxy*; the evidence source string says so. A
licensed OIS feed can be dropped into the same schema instead.
"""
from __future__ import annotations

import csv
import io
import sys
from datetime import date, timedelta
from pathlib import Path

import requests

FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
OUT = Path("data/policy_curve.csv")


def parse_fred(text: str) -> list[tuple[str, float]]:
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return []
    out = []
    for row in rows[1:]:
        if len(row) < 2:
            continue
        try:
            out.append((str(date.fromisoformat(row[0])), float(row[1])))
        except (ValueError, TypeError):
            continue
    return out


def build_curve(sofr: list[tuple[str, float]], two: list[tuple[str, float]],
                ten: list[tuple[str, float]]) -> list[dict[str, str]]:
    by_date = {}
    for series, rows in (("SOFR", sofr), ("2Y", two), ("10Y", ten)):
        for d, v in rows:
            by_date.setdefault(d, {})[series] = v
    out = []
    for d in sorted(by_date):
        vals = by_date[d]
        avail = (date.fromisoformat(d) + timedelta(days=1)).isoformat()
        for tenor in ("2Y", "10Y"):
            if tenor in vals:
                out.append({"series_id": "USD", "tenor": tenor, "date": d,
                            "value": f"{vals[tenor]:.4f}", "available_at": avail,
                            "source": "FRED Treasury/SOFR policy-path proxy (not term OIS)"})
        if "SOFR" in vals:
            out.append({"series_id": "USD", "tenor": "SOFR", "date": d,
                        "value": f"{vals['SOFR']:.4f}", "available_at": avail,
                        "source": "FRED SOFR overnight policy proxy (not term OIS)"})
    return out


def main() -> int:
    series = {}
    for sid in ("SOFR", "DGS2", "DGS10"):
        r = requests.get(FRED.format(sid=sid), timeout=30)
        r.raise_for_status()
        series[sid] = parse_fred(r.text)
    rows = build_curve(series["SOFR"], series["DGS2"], series["DGS10"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["series_id", "tenor", "date", "value",
                                            "available_at", "source"])
        w.writeheader(); w.writerows(rows)
    print(f"wrote {len(rows)} rows to {OUT} (policy-path proxy, not term OIS)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
