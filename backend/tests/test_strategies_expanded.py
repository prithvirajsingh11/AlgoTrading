import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from backend.app.data.loader import OHLCVBar
from backend.app.backtesting.orders import SignalType
from backend.app.strategies.momentum import TimeSeriesMomentumStrategy
from backend.app.strategies.mean_reversion import MeanReversionStrategy
from backend.app.strategies.pairs_trading import PairsTradingStrategy


# ---------------------------------------------------------------------------
# 1. Time-Series Momentum Strategy Tests
# ---------------------------------------------------------------------------

def test_time_series_momentum_validation():
    with pytest.raises(ValueError, match="lookback_period must be a positive integer"):
        TimeSeriesMomentumStrategy(symbol="AAPL", lookback_period=0)

    with pytest.raises(ValueError, match="must be greater than exit_threshold"):
        TimeSeriesMomentumStrategy(symbol="AAPL", entry_threshold=0.01, exit_threshold=0.02)


def test_time_series_momentum_signals():
    strat = TimeSeriesMomentumStrategy(
        symbol="AAPL",
        lookback_period=3,
        entry_threshold=0.05,  # +5% return
        exit_threshold=-0.02, # -2% return
        stop_loss_pct=0.05,
    )

    dates = pd.date_range("2023-01-01", periods=10)
    # Day 0: 100, Day 1: 100, Day 2: 100, Day 3: 100 -> return over 3 days is 0.0
    # Day 4: 110 -> return vs Day 1 is (110 - 100)/100 = 10% > 5% -> BUY!
    # Day 5: 112 -> continuation
    # Day 6: 105 -> return vs Day 3 is (105 - 100)/100 = 5%
    # Day 7: 95  -> return vs Day 4 is (95 - 110)/110 = -13.6% < -2% -> SELL!
    prices = [100.0, 100.0, 100.0, 100.0, 110.0, 112.0, 105.0, 95.0, 96.0, 97.0]
    df = pd.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": prices,
        "low": prices,
        "close": prices,
        "volume": [1000] * 10,
    })

    # Warmup bars: length 1 to 3 return None
    for i in range(3):
        bar = OHLCVBar(dates[i], prices[i], prices[i], prices[i], prices[i], 1000)
        assert strat.generate_signal(bar, df.iloc[: i + 1]) is None

    # Day 4: return is +10% -> BUY signal
    bar4 = OHLCVBar(dates[4], prices[4], prices[4], prices[4], prices[4], 1000)
    sig4 = strat.generate_signal(bar4, df.iloc[:5])
    assert sig4 is not None
    assert sig4.signal_type == SignalType.BUY
    assert sig4.stop_loss_price == pytest.approx(110.0 * 0.95)

    # Day 5: already long, no duplicate BUY
    bar5 = OHLCVBar(dates[5], prices[5], prices[5], prices[5], prices[5], 1000)
    assert strat.generate_signal(bar5, df.iloc[:6]) is None

    # Day 7: return drops to -13.6% -> SELL signal
    bar7 = OHLCVBar(dates[7], prices[7], prices[7], prices[7], prices[7], 1000)
    sig7 = strat.generate_signal(bar7, df.iloc[:8])
    assert sig7 is not None
    assert sig7.signal_type == SignalType.SELL


# ---------------------------------------------------------------------------
# 2. Mean Reversion Strategy Tests
# ---------------------------------------------------------------------------

def test_mean_reversion_validation():
    with pytest.raises(ValueError, match="lookback_period must be at least 2"):
        MeanReversionStrategy(symbol="AAPL", lookback_period=1)

    with pytest.raises(ValueError, match="must be strictly less than exit_z_score"):
        MeanReversionStrategy(symbol="AAPL", entry_z_score=0.5, exit_z_score=-0.5)


def test_mean_reversion_z_score_and_signals():
    strat = MeanReversionStrategy(
        symbol="AAPL",
        lookback_period=5,
        entry_z_score=-1.5,
        exit_z_score=0.0,
    )

    # Test static z-score calculation: price=90, mean=100, std=10 -> z = -1.0
    z = MeanReversionStrategy.calculate_z_score(90.0, 100.0, 10.0)
    assert pytest.approx(z, 1e-4) == -1.0

    # Construct price series:
    # 5 bars at 100.0 (std is 0)
    # Then drop to 80.0
    dates = pd.date_range("2023-01-01", periods=10)
    prices = [100.0, 102.0, 98.0, 101.0, 99.0, 85.0, 86.0, 100.0, 101.0, 102.0]
    df = pd.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": prices,
        "low": prices,
        "close": prices,
        "volume": [1000] * 10,
    })

    # Warmup check: less than 5 bars return None
    for i in range(4):
        bar = OHLCVBar(dates[i], prices[i], prices[i], prices[i], prices[i], 1000)
        assert strat.generate_signal(bar, df.iloc[: i + 1]) is None

    # Bar 5 (index 5, price=85): mean of indices 1..5 is around 97.0, std ~6.8
    # z-score is around (85 - 97) / 6.8 ~ -1.76 <= -1.5 -> BUY signal!
    bar5 = OHLCVBar(dates[5], prices[5], prices[5], prices[5], prices[5], 1000)
    sig5 = strat.generate_signal(bar5, df.iloc[:6])
    assert sig5 is not None
    assert sig5.signal_type == SignalType.BUY
    assert sig5.metadata["z_score"] <= -1.5

    # Bar 7 (price=100): price reverts to mean -> SELL signal!
    bar7 = OHLCVBar(dates[7], prices[7], prices[7], prices[7], prices[7], 1000)
    sig7 = strat.generate_signal(bar7, df.iloc[:8])
    assert sig7 is not None
    assert sig7.signal_type == SignalType.SELL


# ---------------------------------------------------------------------------
# 3. Pairs Trading Strategy Tests
# ---------------------------------------------------------------------------

def test_pairs_trading_spread_and_hedge_ratio():
    # Asset 1 and Asset 2 perfectly cointegrated: P1 = 2 * P2 + 5
    p2 = pd.Series([50.0, 52.0, 51.0, 53.0, 55.0, 54.0])
    p1 = 2.0 * p2 + 5.0

    beta = PairsTradingStrategy.estimate_hedge_ratio(p1, p2)
    assert pytest.approx(beta, 1e-4) == 2.0

    spread = PairsTradingStrategy.calculate_spread(p1, p2, beta)
    # Spread should be constant 5.0
    for s in spread:
        assert pytest.approx(s, 1e-4) == 5.0


def test_pairs_trading_signals():
    strat = PairsTradingStrategy(
        symbol="AAPL",
        hedge_symbol="MSFT",
        lookback_period=5,
        entry_threshold=1.5,
        exit_threshold=0.0,
        fixed_hedge_ratio=1.0,
    )

    dates = pd.date_range("2023-01-01", periods=8)
    # P1 and P2 closely track each other at 100, spread is 0
    p1 = [100.0, 100.0, 100.0, 100.0, 100.0, 90.0, 99.0, 100.0]
    p2 = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]

    df = pd.DataFrame({
        "timestamp": dates,
        "open": p1,
        "high": p1,
        "low": p1,
        "close": p1,
        "volume": [1000] * 8,
        "hedge_close": p2,
    })

    # Bar 5: P1 drops to 90 while P2 stays at 100. Spread = -10. Z-score <= -1.5 -> BUY P1
    bar5 = OHLCVBar(dates[5], p1[5], p1[5], p1[5], p1[5], 1000)
    sig5 = strat.generate_signal(bar5, df.iloc[:6])
    assert sig5 is not None
    assert sig5.signal_type == SignalType.BUY
    assert sig5.metadata["hedge_symbol"] == "MSFT"

    # Bar 7: P1 reverts back to 100, spread returns to 0 -> SELL
    bar7 = OHLCVBar(dates[7], p1[7], p1[7], p1[7], p1[7], 1000)
    sig7 = strat.generate_signal(bar7, df.iloc[:8])
    assert sig7 is not None
    assert sig7.signal_type == SignalType.SELL
