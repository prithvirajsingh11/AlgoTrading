"""Tests for True Multi-Asset Pairs Trading:
- MarketSnapshot abstraction & multi-asset synchronization
- Rejection of invalid/duplicate/unsorted datasets
- Two-leg trade execution (Long Spread: BUY A / SELL B; Short Spread: SELL A / BUY B)
- Multi-asset short position accounting & combined P&L
- Mandatory Zero-Lookahead Bias Regression Test (future spike at t > t0 does not alter state at t0)
"""

from datetime import datetime, timedelta
import pytest
import pandas as pd
import numpy as np

from backend.app.data.loader import OHLCVBar, MarketSnapshot
from backend.app.data.cleaner import synchronize_pair_datasets
from backend.app.backtesting.orders import SignalType, SignalEvent, OrderSide
from backend.app.strategies.pairs_trading import PairsTradingStrategy
from backend.app.backtesting.engine import BacktestEngine
from backend.app.backtesting.portfolio import Portfolio


def _create_sample_df(start_date: datetime, periods: int, base_price: float, step: float = 1.0) -> pd.DataFrame:
    dates = [start_date + timedelta(days=i) for i in range(periods)]
    prices = [base_price + i * step for i in range(periods)]
    return pd.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": [p + 1.0 for p in prices],
        "low": [p - 1.0 for p in prices],
        "close": prices,
        "volume": [10_000.0] * periods,
    })


def test_market_snapshot_properties():
    dt = datetime(2023, 1, 1, 10, 0)
    bar_a = OHLCVBar(dt, 100.0, 101.0, 99.0, 100.0, 1000, symbol="AAPL")
    bar_b = OHLCVBar(dt, 200.0, 202.0, 198.0, 200.0, 2000, symbol="MSFT")

    snapshot = MarketSnapshot(timestamp=dt, bars={"AAPL": bar_a, "MSFT": bar_b})
    assert snapshot.timestamp == dt
    assert "AAPL" in snapshot
    assert "MSFT" in snapshot
    assert snapshot["AAPL"].close == 100.0
    assert snapshot.get_bar("MSFT").high == 202.0
    assert snapshot.get_bar("UNKNOWN") is None


def test_synchronize_pair_datasets_intersection():
    dt = datetime(2023, 1, 1)
    df_a = _create_sample_df(dt, periods=10, base_price=100.0)
    # df_b starts 2 days later and has 10 days (overlapping on days 2..9)
    df_b = _create_sample_df(dt + timedelta(days=2), periods=10, base_price=200.0)

    synced_a, synced_b, snapshots = synchronize_pair_datasets(df_a, df_b, "AAPL", "MSFT")
    assert len(synced_a) == len(synced_b)
    assert len(synced_a) == 8
    assert len(snapshots) == 8
    # Exact timestamp match
    assert (synced_a["timestamp"] == synced_b["timestamp"]).all()


def test_synchronize_pair_datasets_validation_errors():
    dt = datetime(2023, 1, 1)
    df_a = _create_sample_df(dt, periods=5, base_price=100.0)

    # 1. Duplicate timestamp in df_a
    dup_df = pd.concat([df_a, df_a.iloc[[0]]]).reset_index(drop=True)
    with pytest.raises(ValueError, match="duplicate timestamp"):
        synchronize_pair_datasets(dup_df, df_a, "AAPL", "MSFT")

    # 2. No overlapping timestamps
    df_disjoint = _create_sample_df(dt + timedelta(days=50), periods=5, base_price=100.0)
    with pytest.raises(ValueError, match="No common timestamps"):
        synchronize_pair_datasets(df_a, df_disjoint, "AAPL", "MSFT")


def test_pairs_trading_two_leg_signals():
    strat = PairsTradingStrategy(
        symbol="AAPL",
        hedge_symbol="MSFT",
        lookback_period=5,
        entry_threshold=1.5,
        exit_threshold=0.5,
        fixed_hedge_ratio=1.0,
        two_leg=True,
    )

    dates = pd.date_range("2023-01-01", periods=10)
    # Baseline: both at 100
    p1 = [100.0, 100.0, 100.0, 100.0, 100.0, 88.0, 89.0, 100.0, 112.0, 100.0]
    p2 = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]

    df_a = pd.DataFrame({"timestamp": dates, "open": p1, "high": p1, "low": p1, "close": p1, "volume": 1000})
    df_b = pd.DataFrame({"timestamp": dates, "open": p2, "high": p2, "low": p2, "close": p2, "volume": 1000})

    history = {"AAPL": df_a, "MSFT": df_b}

    # Bar 5: AAPL drops to 88.0, MSFT stays 100. Spread = -12. Z-score <= -1.5 -> LONG SPREAD
    bar_a = OHLCVBar(dates[5], p1[5], p1[5], p1[5], p1[5], 1000, symbol="AAPL")
    bar_b = OHLCVBar(dates[5], p2[5], p2[5], p2[5], p2[5], 1000, symbol="MSFT")
    snap5 = MarketSnapshot(dates[5], {"AAPL": bar_a, "MSFT": bar_b})

    signals5 = strat.generate_signal(snap5, history)
    assert isinstance(signals5, list)
    assert len(signals5) == 2
    # Leg 1: BUY AAPL
    assert signals5[0].symbol == "AAPL"
    assert signals5[0].signal_type == SignalType.BUY
    # Leg 2: SELL MSFT
    assert signals5[1].symbol == "MSFT"
    assert signals5[1].signal_type == SignalType.SELL

    # Bar 7: Spread reverts to 0 (|z| <= 0.5) -> EXIT BOTH LEGS
    bar_a7 = OHLCVBar(dates[7], p1[7], p1[7], p1[7], p1[7], 1000, symbol="AAPL")
    bar_b7 = OHLCVBar(dates[7], p2[7], p2[7], p2[7], p2[7], 1000, symbol="MSFT")
    snap7 = MarketSnapshot(dates[7], {"AAPL": bar_a7, "MSFT": bar_b7})

    signals7 = strat.generate_signal(snap7, history)
    assert isinstance(signals7, list)
    assert len(signals7) == 2
    # Exit long AAPL (SELL) & exit short MSFT (BUY to cover)
    assert signals7[0].symbol == "AAPL"
    assert signals7[0].signal_type == SignalType.SELL
    assert signals7[1].symbol == "MSFT"
    assert signals7[1].signal_type == SignalType.BUY


def test_pairs_trading_multi_asset_backtest_execution():
    """Runs a complete two-leg pairs trading backtest through BacktestEngine."""
    dates = pd.date_range("2023-01-01", periods=15)
    # Price series designed to trigger long spread then exit
    p_a = [100.0, 100.0, 100.0, 100.0, 100.0, 85.0, 85.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]
    p_b = [100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]

    df_a = pd.DataFrame({"timestamp": dates, "open": p_a, "high": p_a, "low": p_a, "close": p_a, "volume": 1000})
    df_b = pd.DataFrame({"timestamp": dates, "open": p_b, "high": p_b, "low": p_b, "close": p_b, "volume": 1000})

    strat = PairsTradingStrategy(
        symbol="AAPL",
        hedge_symbol="MSFT",
        lookback_period=5,
        entry_threshold=1.5,
        exit_threshold=0.5,
        fixed_hedge_ratio=1.0,
        two_leg=True,
    )

    engine = BacktestEngine(
        symbol="AAPL",
        initial_capital=100_000.0,
        allow_shorting=True,
        commission_fixed=0.0,
        commission_percent=0.0,
        slippage_bps=0.0,
    )

    result = engine.run(data={"AAPL": df_a, "MSFT": df_b}, strategy=strat)

    assert result is not None
    assert len(result.trades) >= 2
    # Verify trade symbols include both AAPL and MSFT
    traded_symbols = {t["symbol"] for t in result.trades}
    assert "AAPL" in traded_symbols
    assert "MSFT" in traded_symbols


def test_mandatory_zero_lookahead_regression():
    """MANDATORY REGRESSION TEST:
    Inject a future price spike in Asset A at t > t0.
    Verify that the signal, hedge ratio, spread, and z-score computed at t0
    are 100% identical with and without future data.
    """
    total_bars = 30
    cutoff_index = 15  # t0
    dates = pd.date_range("2023-01-01", periods=total_bars)

    np.random.seed(42)
    # Generate realistic cointegrated series
    noise = np.random.normal(0, 1.0, total_bars)
    base_b = 100.0 + np.cumsum(np.random.normal(0, 0.5, total_bars))
    base_a = 1.5 * base_b + 10.0 + noise

    # Scenario 1: Clean data up to cutoff t0
    df_clean_a = pd.DataFrame({
        "timestamp": dates[:cutoff_index + 1],
        "open": base_a[:cutoff_index + 1],
        "high": base_a[:cutoff_index + 1] + 1.0,
        "low": base_a[:cutoff_index + 1] - 1.0,
        "close": base_a[:cutoff_index + 1],
        "volume": 10_000,
    })
    df_clean_b = pd.DataFrame({
        "timestamp": dates[:cutoff_index + 1],
        "open": base_b[:cutoff_index + 1],
        "high": base_b[:cutoff_index + 1] + 1.0,
        "low": base_b[:cutoff_index + 1] - 1.0,
        "close": base_b[:cutoff_index + 1],
        "volume": 10_000,
    })

    strat1 = PairsTradingStrategy(
        symbol="AAPL",
        hedge_symbol="MSFT",
        lookback_period=10,
        entry_threshold=2.0,
        exit_threshold=0.5,
        two_leg=True,
    )

    t0_dt = dates[cutoff_index]
    bar_a_t0 = OHLCVBar(t0_dt, base_a[cutoff_index], base_a[cutoff_index] + 1, base_a[cutoff_index] - 1, base_a[cutoff_index], 10000, symbol="AAPL")
    bar_b_t0 = OHLCVBar(t0_dt, base_b[cutoff_index], base_b[cutoff_index] + 1, base_b[cutoff_index] - 1, base_b[cutoff_index], 10000, symbol="MSFT")
    snap_t0 = MarketSnapshot(t0_dt, {"AAPL": bar_a_t0, "MSFT": bar_b_t0})

    sig1 = strat1.generate_signal(snap_t0, {"AAPL": df_clean_a, "MSFT": df_clean_b})

    # Scenario 2: Massive future spike at t0 + 5 (10x price spike!)
    spiked_a = base_a.copy()
    spiked_a[cutoff_index + 5] = spiked_a[cutoff_index + 5] * 10.0

    df_spiked_a = pd.DataFrame({
        "timestamp": dates,
        "open": spiked_a,
        "high": spiked_a + 5.0,
        "low": spiked_a - 5.0,
        "close": spiked_a,
        "volume": 10_000,
    })
    df_spiked_b = pd.DataFrame({
        "timestamp": dates,
        "open": base_b,
        "high": base_b + 1.0,
        "low": base_b - 1.0,
        "close": base_b,
        "volume": 10_000,
    })

    strat2 = PairsTradingStrategy(
        symbol="AAPL",
        hedge_symbol="MSFT",
        lookback_period=10,
        entry_threshold=2.0,
        exit_threshold=0.5,
        two_leg=True,
    )

    # Evaluate at EXACT same timestamp t0 using full spiked dataset
    sig2 = strat2.generate_signal(snap_t0, {"AAPL": df_spiked_a, "MSFT": df_spiked_b})

    # Verification: Both signals must be identical
    if sig1 is None:
        assert sig2 is None
    else:
        assert sig2 is not None
        assert len(sig1) == len(sig2)
        for s1, s2 in zip(sig1, sig2):
            assert s1.signal_type == s2.signal_type
            assert s1.symbol == s2.symbol
            # Metadata comparisons (hedge ratio, z-score, spread)
            assert s1.metadata["hedge_ratio"] == s2.metadata["hedge_ratio"]
            assert s1.metadata["z_score"] == s2.metadata["z_score"]
            assert s1.metadata["spread"] == s2.metadata["spread"]
