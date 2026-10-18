"""The point-in-time cursor (lesson 02 §1).

The structural claim being tested: a strategy handed a `DataView` at session `t` cannot reach
session `t+1` by any route. That is what makes the look-ahead defence a property of the engine
rather than a code-review habit.
"""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from liquid_atm_quant.backtest.panel import DataView, FutureDataError, Panel

START = date(2026, 1, 5)


def sessions(n: int) -> list[date]:
    """Weekday-only sessions, which is all these tests need from a calendar."""
    out, day = [], START
    while len(out) < n:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


def make_panel(n: int = 40, symbols=("AAA", "BBB"), segment_break: dict | None = None) -> Panel:
    days = sessions(n)
    rows = []
    for j, symbol in enumerate(symbols):
        for i, day in enumerate(days):
            close = 100.0 + i + j * 10
            segment = 0
            if segment_break and symbol in segment_break and i >= segment_break[symbol]:
                segment = 1
            rows.append({"trade_date": day, "symbol": symbol, "open": close - 0.5,
                         "high": close + 1.0, "low": close - 1.0, "close": close,
                         "volume": 1_000_000 + i, "adj_factor": 1.0, "segment_id": segment})
    return Panel.from_frame(pd.DataFrame(rows), days)


def test_history_stops_at_today():
    panel = make_panel()
    view = panel.view(10)
    closes = view.history("close", "AAA")
    assert len(closes) == 11
    assert closes[-1] == panel.column("close")[10, panel.index["AAA"]]


def test_asking_for_a_future_session_raises():
    view = make_panel().view(10)
    assert view.at(view.panel.sessions[10]) == 10
    with pytest.raises(FutureDataError):
        view.at(view.panel.sessions[11])


def test_lookback_is_clipped_at_the_start_of_the_panel():
    view = make_panel().view(3)
    assert len(view.history("close", "AAA", lookback=50)) == 4


def test_truncating_the_panel_gives_the_same_view_values():
    """The truncation property from lesson 01 §7, applied to the cursor itself: a view at t built
    from the full panel and one built from a panel that ends at t must agree."""
    panel = make_panel(40)
    t = 20
    truncated = Panel.from_frame(
        pd.DataFrame([{"trade_date": d, "symbol": s, "open": panel.arrays["open"][i, j],
                       "high": panel.arrays["high"][i, j], "low": panel.arrays["low"][i, j],
                       "close": panel.arrays["close"][i, j],
                       "volume": panel.arrays["volume"][i, j], "adj_factor": 1.0, "segment_id": 0}
                      for i, d in enumerate(panel.sessions[:t + 1])
                      for j, s in enumerate(panel.symbols)]),
        panel.sessions[:t + 1])
    assert np.allclose(panel.view(t).history("close", "AAA"),
                       truncated.view(t).history("close", "AAA"))
    assert panel.view(t).adv("AAA", 20) == pytest.approx(truncated.view(t).adv("AAA", 20))


def test_adv_uses_only_trailing_sessions():
    """Sizing must never be capped against tomorrow's volume: that is look-ahead in the direction
    that flatters the backtest (lesson 02 §3)."""
    panel = make_panel()
    view = panel.view(25)
    j = panel.index["AAA"]
    expected = float((panel.column("volume")[6:26, j] * panel.column("close")[6:26, j]).mean())
    assert view.adv("AAA", 20) == pytest.approx(expected)


def test_same_segment_rejects_a_window_spanning_a_ticker_reuse():
    """No indicator window may straddle two companies that shared a ticker (lesson 01 §5b)."""
    panel = make_panel(40, segment_break={"BBB": 20})
    assert panel.view(30).same_segment("AAA", 25) is True
    assert panel.view(30).same_segment("BBB", 25) is False
    assert panel.view(30).same_segment("BBB", 5) is True


def test_adjusted_differs_from_raw_when_a_factor_is_set():
    days = sessions(5)
    rows = [{"trade_date": d, "symbol": "SPL", "open": 400.0, "high": 401.0, "low": 399.0,
             "close": 400.0, "volume": 1_000, "adj_factor": 0.25, "segment_id": 0} for d in days]
    panel = Panel.from_frame(pd.DataFrame(rows), days)
    view = panel.view(4)
    assert view.latest("close", "SPL") == 400.0                  # raw: what orders must use
    assert view.latest("close", "SPL", adjusted=True) == 100.0   # adjusted: what returns must use


def test_universe_defaults_to_everything_that_traded():
    panel = make_panel()
    assert panel.view(5).universe() == ["AAA", "BBB"]


def test_dividends_are_reconstructed_from_the_adjustment_factor():
    """A 0.4% upward step in adj_factor on a $100 stock is a $0.40 distribution, not a split."""
    days = sessions(6)
    factors = [0.996, 0.996, 1.0, 1.0, 1.0, 1.0]
    rows = [{"trade_date": d, "symbol": "DIV", "open": 100.0, "high": 100.0, "low": 100.0,
             "close": 100.0, "volume": 1_000, "adj_factor": f, "segment_id": 0}
            for d, f in zip(days, factors, strict=True)]
    panel = Panel.from_frame(pd.DataFrame(rows), days)
    schedule = panel.dividends()["DIV"]
    assert list(schedule) == [2]
    assert schedule[2] == pytest.approx(100.0 * (1.0 / 0.996 - 1.0))


def test_a_split_sized_factor_step_is_not_treated_as_a_dividend():
    days = sessions(4)
    factors = [0.25, 0.25, 1.0, 1.0]
    rows = [{"trade_date": d, "symbol": "SPL", "open": 100.0, "high": 100.0, "low": 100.0,
             "close": 100.0, "volume": 1_000, "adj_factor": f, "segment_id": 0}
            for d, f in zip(days, factors, strict=True)]
    panel = Panel.from_frame(pd.DataFrame(rows), days)
    assert "SPL" not in panel.dividends()


def test_view_outside_the_panel_raises():
    panel = make_panel(10)
    with pytest.raises(IndexError):
        DataView(panel, 10)
