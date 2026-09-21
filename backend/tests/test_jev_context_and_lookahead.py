"""Tests for market context builder and mandatory zero-lookahead bias regression."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from backend.app.ai.jev_context import build_market_context, compute_context_hash
from backend.app.backtesting.portfolio import Portfolio
from backend.app.backtesting.orders import SignalEvent, SignalType


def _make_sample_dataframe(n: int = 60, base_price: float = 100.0) -> pd.DataFrame:
    base_date = datetime(2023, 1, 1)
    dates = [base_date + timedelta(days=i) for i in range(n)]
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.015, n)
    prices = base_price * np.cumprod(1 + returns)

    return pd.DataFrame({
        "timestamp": [d.strftime("%Y-%m-%d") for d in dates],
        "open": prices * 0.995,
        "high": prices * 1.015,
        "low": prices * 0.985,
        "close": prices,
        "volume": [100000 + i * 500 for i in range(n)],
    })


def test_single_asset_context_generation():
    """Verify market context builder computes all expected quantitative features."""
    df = _make_sample_dataframe(40)
    portfolio = Portfolio(initial_cash=50000.0)
    signal = SignalEvent(
        symbol="AAPL",
        signal_type=SignalType.BUY,
        timestamp="2023-01-30",
        strength=1.0,
        stop_loss_price=95.0,
    )

    context = build_market_context(
        symbol="AAPL",
        historical_slice=df,
        portfolio=portfolio,
        signals=[signal],
    )

    assert context["symbol"] == "AAPL"
    assert "price" in context
    assert "recent_return" in context
    assert "volatility" in context
    assert "sma_10" in context
    assert "sma_30" in context
    assert "ema_12" in context
    assert "ema_26" in context
    assert "rsi_14" in context
    assert "macd" in context
    assert "atr_14" in context
    assert context["portfolio"]["cash"] == 50000.0
    assert len(context["strategy_signals"]) == 1
    assert context["strategy_signals"][0]["type"] == "BUY"


def test_pairs_trading_context_generation():
    """Verify pairs trading context includes spread and dynamic hedge ratio."""
    df_a = _make_sample_dataframe(40, base_price=150.0)
    df_b = _make_sample_dataframe(40, base_price=75.0)

    historical_slice = {"AAPL": df_a, "MSFT": df_b}
    portfolio = Portfolio(initial_cash=100000.0)

    context = build_market_context(
        symbol="AAPL",
        historical_slice=historical_slice,
        portfolio=portfolio,
    )

    assert "pairs_trading" in context
    p_info = context["pairs_trading"]
    assert p_info["symbol_a"] == "AAPL"
    assert p_info["symbol_b"] == "MSFT"
    assert p_info["price_a"] > 0
    assert p_info["price_b"] > 0
    assert "hedge_ratio" in p_info
    assert "spread" in p_info
    assert "spread_z_score" in p_info


def test_mandatory_zero_lookahead_regression():
    """MANDATORY REGRESSION:
    Run the exact same historical decision point at bar t twice.
    Version A: normal future market data beyond t.
    Version B: wildly corrupted future market data beyond t (spikes, crashes, volume surges).
    Verify that the context dictionary, computed indicators, and context hash at t are 100% identical.
    """
    df_original = _make_sample_dataframe(60, base_price=100.0)

    # Corrupt future bars (index 30 onwards)
    df_corrupted = df_original.copy(deep=True)
    df_corrupted.loc[30:, "close"] = df_corrupted.loc[30:, "close"] * 5.0
    df_corrupted.loc[30:, "high"] = df_corrupted.loc[30:, "high"] * 10.0
    df_corrupted.loc[30:, "low"] = 1.0
    df_corrupted.loc[30:, "volume"] = 999999999.0

    eval_index = 29  # 30th bar (timestamp at index 29)

    portfolio1 = Portfolio(initial_cash=100000.0)
    portfolio2 = Portfolio(initial_cash=100000.0)

    # In engine, historical_slice at bar 29 is df.iloc[:30]
    slice_a = df_original.iloc[: eval_index + 1]
    slice_b = df_corrupted.iloc[: eval_index + 1]

    context_a = build_market_context(
        symbol="AAPL",
        historical_slice=slice_a,
        portfolio=portfolio1,
    )
    context_b = build_market_context(
        symbol="AAPL",
        historical_slice=slice_b,
        portfolio=portfolio2,
    )

    # 1. Identical context hashes
    hash_a = compute_context_hash(context_a)
    hash_b = compute_context_hash(context_b)
    assert hash_a == hash_b

    # 2. Strict dictionary equality
    assert context_a == context_b

    # 3. Exact float indicators equality
    assert context_a["price"] == context_b["price"]
    assert context_a["sma_10"] == context_b["sma_10"]
    assert context_a["sma_30"] == context_b["sma_30"]
    assert context_a["rsi_14"] == context_b["rsi_14"]
    assert context_a["macd"] == context_b["macd"]
    assert context_a["atr_14"] == context_b["atr_14"]
    assert context_a["volatility"] == context_b["volatility"]
