import numpy as np
import pandas as pd
import pytest

from liquid_atm_quant.data.pit import LookAheadError, assert_no_lookahead


@pytest.fixture
def prices():
    idx = pd.bdate_range("2024-01-01", periods=120)
    rng = np.random.default_rng(7)
    return pd.DataFrame({"close": 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(idx))))}, index=idx)


def test_honest_trailing_signal_passes(prices):
    assert_no_lookahead(lambda df: df["close"].rolling(20).mean(), prices)


def test_planted_lookahead_is_caught(prices):
    # The classic bug: tomorrow's close in today's signal.
    with pytest.raises(LookAheadError):
        assert_no_lookahead(lambda df: df["close"].shift(-1), prices)


def test_centered_rolling_window_is_caught(prices):
    with pytest.raises(LookAheadError):
        assert_no_lookahead(lambda df: df["close"].rolling(21, center=True).mean(), prices)


def test_whole_sample_normalisation_is_caught(prices):
    # Subtly wrong: scaling by the full-sample mean leaks the future into every row.
    with pytest.raises(LookAheadError):
        assert_no_lookahead(lambda df: df["close"] / df["close"].mean(), prices)


def test_backfill_is_caught(prices):
    gapped = prices.copy()
    gapped.iloc[50] = np.nan
    # checks high enough to test every date: the leak only shows at the gap itself.
    with pytest.raises(LookAheadError):
        assert_no_lookahead(lambda df: df["close"].bfill(), gapped, checks=1000)


def test_multi_column_signals_supported(prices):
    def signals(df: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({"ma": df["close"].rolling(10).mean(), "ret": df["close"].pct_change()})

    assert_no_lookahead(signals, prices)


def test_requires_sorted_index(prices):
    with pytest.raises(ValueError):
        assert_no_lookahead(lambda df: df["close"], prices.iloc[::-1])
