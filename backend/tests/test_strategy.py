import pytest
from datetime import datetime
import pandas as pd
from backend.app.data.loader import OHLCVBar
from backend.app.strategies.momentum import MovingAverageCrossStrategy
from backend.app.backtesting.orders import SignalType


def test_strategy_parameter_validation():
    # fast >= slow raises error
    with pytest.raises(ValueError, match="must be strictly less than"):
        MovingAverageCrossStrategy(symbol="AAPL", fast_period=20, slow_period=10)

    # non-positive raises error
    with pytest.raises(ValueError, match="must be positive"):
        MovingAverageCrossStrategy(symbol="AAPL", fast_period=0, slow_period=10)


def test_strategy_warmup_and_signals():
    strategy = MovingAverageCrossStrategy(symbol="AAPL", fast_period=3, slow_period=5)
    # slow_period is 5, warmup_period is 6

    # Construct price series:
    # 5 bars flat at 100
    # bar 6 jumps to 110 (triggers fast MA > slow MA: Golden Cross)
    prices = [100.0, 100.0, 100.0, 100.0, 100.0, 110.0, 120.0, 90.0, 80.0]
    dates = pd.date_range("2023-01-01", periods=len(prices))

    rows = []
    for dt, p in zip(dates, prices):
        rows.append({"timestamp": dt, "open": p, "high": p, "low": p, "close": p, "volume": 1000})
    df = pd.DataFrame(rows)

    # Bars 0 to 4 (length 1 to 5) should emit None due to warmup
    for i in range(5):
        bar = OHLCVBar(timestamp=dates[i], open=prices[i], high=prices[i], low=prices[i], close=prices[i], volume=1000)
        signal = strategy.generate_signal(bar, df.iloc[: i + 1])
        assert signal is None

    # Bar 5 (6th bar): jump to 110 triggers fast_ma > slow_ma -> BUY
    bar5 = OHLCVBar(timestamp=dates[5], open=110.0, high=110.0, low=110.0, close=110.0, volume=1000)
    sig5 = strategy.generate_signal(bar5, df.iloc[: 6])
    assert sig5 is not None
    assert sig5.signal_type == SignalType.BUY
    assert sig5.metadata["crossover"] == "golden_cross"

    # Bar 6: continuation upward (120.0), already bought -> no duplicate BUY
    bar6 = OHLCVBar(timestamp=dates[6], open=120.0, high=120.0, low=120.0, close=120.0, volume=1000)
    sig6 = strategy.generate_signal(bar6, df.iloc[: 7])
    assert sig6 is None

    # Bar 7: drops to 90.0
    bar7 = OHLCVBar(timestamp=dates[7], open=90.0, high=90.0, low=90.0, close=90.0, volume=1000)
    sig7 = strategy.generate_signal(bar7, df.iloc[: 8])

    # Bar 8: drops to 80.0, fast MA drops below slow MA -> SELL
    bar8 = OHLCVBar(timestamp=dates[8], open=80.0, high=80.0, low=80.0, close=80.0, volume=1000)
    sig8 = strategy.generate_signal(bar8, df.iloc[: 9])
    assert sig8 is not None
    assert sig8.signal_type == SignalType.SELL
    assert sig8.metadata["crossover"] == "death_cross"
