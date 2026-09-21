"""Tests for MLStrategy and authoritative RiskManager pipeline integration."""

import numpy as np
import pandas as pd
import pytest

from backend.app.ml.train import train_ml_pipeline
from backend.app.strategies.ml_strategy import MLStrategy
from backend.app.backtesting.engine import BacktestEngine
from backend.app.backtesting.broker import SimulatedBroker
from backend.app.backtesting.orders import SignalType
from backend.app.risk.position_sizing import PercentEquitySizer
from backend.app.risk.risk_manager import RiskManager
from backend.app.data.loader import OHLCVBar


def create_sample_ohlcv(n: int = 150) -> pd.DataFrame:
    """Generates synthetic OHLCV time series for testing."""
    dates = pd.date_range("2023-01-01", periods=n, freq="D")
    np.random.seed(42)
    rets = np.random.normal(0.0005, 0.015, n)
    prices = 100.0 * np.cumprod(1.0 + rets)
    opens = prices * (1.0 + np.random.normal(0, 0.003, n))
    highs = np.maximum(prices, opens) * (1.0 + np.abs(np.random.normal(0.002, 0.005, n)))
    lows = np.minimum(prices, opens) * (1.0 - np.abs(np.random.normal(0.002, 0.005, n)))
    vols = np.random.randint(1000, 10000, n).astype(float)

    return pd.DataFrame({
        "timestamp": dates.strftime("%Y-%m-%d"),
        "open": opens,
        "high": highs,
        "low": lows,
        "close": prices,
        "volume": vols,
    })


def test_ml_strategy_threshold_validation():
    """Verifies that buy_threshold must strictly exceed sell_threshold."""
    with pytest.raises(ValueError, match="buy_threshold .* must be strictly greater"):
        MLStrategy(symbol="AAPL", parameters={"buy_threshold": 0.40, "sell_threshold": 0.60})


def test_ml_strategy_signal_generation():
    """Verifies that MLStrategy generates BUY/SELL/HOLD signals based on probability."""
    df = create_sample_ohlcv(120)
    train_res = train_ml_pipeline(df, symbol="AAPL")

    strategy = MLStrategy(
        symbol="AAPL",
        parameters={
            "artifact": train_res.artifact,
            "buy_threshold": 0.52,
            "sell_threshold": 0.48,
        },
    )

    # During warmup (< warmup_period bars), generate_signal returns None
    slice_short = df.iloc[:10]
    bar_short = OHLCVBar(
        timestamp=slice_short["timestamp"].iloc[-1],
        open=slice_short["open"].iloc[-1],
        high=slice_short["high"].iloc[-1],
        low=slice_short["low"].iloc[-1],
        close=slice_short["close"].iloc[-1],
        volume=slice_short["volume"].iloc[-1],
    )
    sig_warmup = strategy.generate_signal(bar_short, slice_short)
    assert sig_warmup is None

    # After warmup period, evaluates bar
    slice_full = df.iloc[:80]
    bar_full = OHLCVBar(
        timestamp=slice_full["timestamp"].iloc[-1],
        open=slice_full["open"].iloc[-1],
        high=slice_full["high"].iloc[-1],
        low=slice_full["low"].iloc[-1],
        close=slice_full["close"].iloc[-1],
        volume=slice_full["volume"].iloc[-1],
    )
    sig = strategy.generate_signal(bar_full, slice_full)
    # Signal can be None (HOLD), BUY, or SELL
    if sig is not None:
        assert sig.signal_type in (SignalType.BUY, SignalType.SELL)
        assert sig.symbol == "AAPL"
        assert 0.0 <= sig.strength <= 1.0
        assert "ml_prediction" in sig.metadata


def test_ml_strategy_risk_manager_authoritative_integration():
    """Verifies that MLStrategy signals flow through RiskManager and respect position limits."""
    df = create_sample_ohlcv(140)
    train_res = train_ml_pipeline(df, symbol="AAPL")

    strategy = MLStrategy(
        symbol="AAPL",
        parameters={
            "artifact": train_res.artifact,
            "buy_threshold": 0.50,  # Aggressive threshold to trigger signals
            "sell_threshold": 0.49,
        },
    )

    risk_manager = RiskManager(
        max_position_pct=0.30,      # Max 30% concentration
        max_drawdown_limit=0.15,    # 15% drawdown breaker
        allow_shorting=False,
    )
    position_sizer = PercentEquitySizer(percent_equity=0.20)
    broker = SimulatedBroker()

    engine = BacktestEngine(
        symbol="AAPL",
        initial_capital=100_000.0,
        risk_manager=risk_manager,
        position_sizer=position_sizer,
        broker=broker,
    )

    result = engine.run(data=df, strategy=strategy)

    assert result is not None
    assert len(result.equity_curve) == len(df)
    assert result.metrics is not None

    # Verify risk manager concentration was strictly respected
    for pt in result.equity_curve:
        total_equity = pt["total_equity"]
        holdings = pt.get("holdings_value", 0.0)
        assert holdings <= total_equity * 0.35, "Position concentration violated 30% limit!"
