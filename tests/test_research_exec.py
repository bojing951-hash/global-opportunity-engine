from __future__ import annotations

import pandas as pd

from goe.research_exec import _event_date, _ret


def test_event_date_uses_only_bars_up_to_as_of():
    idx = pd.bdate_range("2026-01-01", periods=30)
    y = pd.Series(0.0, index=idx)
    y.iloc[10] = -0.06
    y.iloc[-1] = -0.10  # after a hypothetical as_of below
    r = pd.DataFrame({"X": y})
    as_of = str(idx[20].date())
    assert _event_date(r, "X", as_of) == str(idx[10].date())


def test_ret_returns_none_for_future_or_missing_date():
    idx = pd.bdate_range("2026-01-01", periods=3)
    r = pd.DataFrame({"X": [0.01, 0.02, 0.03]}, index=idx)
    assert _ret(r, "X", str(idx[1].date())) == 0.02
    assert _ret(r, "X", "2026-02-01") is None
    assert _ret(r, "Y", str(idx[1].date())) is None
