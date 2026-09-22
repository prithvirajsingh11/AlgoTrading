"""Integration tests for real-time market data pipeline, bar aggregation, and safety state machine."""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta

from backend.app.paper.bar_builder import BarBuilder
from backend.app.paper.sync import SnapshotSynchronizer
from backend.app.paper.streaming_features import StreamingFeatureEngine
from backend.app.paper.realtime import MarketTick, InMemoryStreamingAdapter
from backend.app.paper.session import (
    PaperTradingSession,
    SessionStatus,
    SessionMode,
    SignalSafetyState,
)
from backend.app.paper.orders import PaperOrderManager
from backend.app.paper.account import PaperAccount
from backend.app.backtesting.portfolio import Portfolio
from backend.app.risk.risk_manager import RiskManager
from backend.app.backtesting.broker import SimulatedBroker
from backend.app.backtesting.orders import Order, OrderType, OrderSide
from backend.app.data.loader import OHLCVBar


def test_tick_to_bar_pipeline():
    """Verify ticks correctly accumulate and close into deterministic bars."""
    bb = BarBuilder(interval="1s")
    base_t = datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)

    # Ingest 3 ticks in second 0
    t1 = MarketTick("AAPL", base_t + timedelta(milliseconds=100), 150.0, 10)
    t2 = MarketTick("AAPL", base_t + timedelta(milliseconds=400), 152.0, 20)
    t3 = MarketTick("AAPL", base_t + timedelta(milliseconds=800), 149.0, 5)

    assert bb.on_tick(t1) is None
    assert bb.on_tick(t2) is None
    assert bb.on_tick(t3) is None

    # Tick in second 1 triggers bar closure for second 0
    t4 = MarketTick("AAPL", base_t + timedelta(milliseconds=1100), 151.0, 15)
    closed = bb.on_tick(t4)

    assert closed is not None
    assert closed.symbol == "AAPL"
    assert closed.open == 150.0
    assert closed.high == 152.0
    assert closed.low == 149.0
    assert closed.close == 149.0
    assert closed.volume == 35.0


def test_streaming_feature_engine_integration():
    """Verify closed bars incrementally update features."""
    engine = StreamingFeatureEngine(symbols=["AAPL"])
    base_t = datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)

    for i in range(engine.warmup_bars + 5):
        bar = OHLCVBar(
            timestamp=base_t + timedelta(minutes=i),
            open=100.0 + i,
            high=102.0 + i,
            low=99.0 + i,
            close=101.0 + i,
            volume=1000.0,
            symbol="AAPL",
        )
        engine.update_bar(bar)

    assert engine.is_warmed_up("AAPL") is True
    feats_df = engine.compute_latest_features("AAPL")
    assert not feats_df.empty
    assert "log_return" in feats_df.columns
    assert "simple_return" in feats_df.columns


def test_multi_asset_synchronization_and_staleness():
    """Verify per-symbol staleness and synchronized multi-asset snapshots."""
    sync = SnapshotSynchronizer(
        symbols=["AAPL", "MSFT"],
        max_desync_seconds=2.0,
    )
    t0 = datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)

    # AAPL bar arrives at t0
    bar_aapl = OHLCVBar(
        timestamp=t0,
        open=150.0,
        high=151.0,
        low=149.0,
        close=150.5,
        volume=1000.0,
        symbol="AAPL",
    )
    sync.update_bar(bar_aapl)

    # Check freshness: AAPL is fresh at t0, MSFT has no data
    assert sync.is_symbol_fresh("AAPL", reference_time=t0) is True
    assert sync.is_symbol_fresh("MSFT", reference_time=t0) is False
    assert "MSFT" in sync.get_stale_symbols(reference_time=t0)

    # Snapshot is not yet synchronized because MSFT is missing
    snap = sync.get_synchronized_snapshot(reference_time=t0)
    assert snap is None

    # MSFT bar arrives within desync window (t0 + 1s)
    bar_msft = OHLCVBar(
        timestamp=t0 + timedelta(seconds=1),
        open=300.0,
        high=302.0,
        low=299.0,
        close=301.0,
        volume=500.0,
        symbol="MSFT",
    )
    sync.update_bar(bar_msft)

    snap2 = sync.get_synchronized_snapshot(reference_time=t0 + timedelta(seconds=1))
    assert snap2 is not None
    assert "AAPL" in snap2.bars
    assert "MSFT" in snap2.bars


def test_signal_safety_state_machine_and_asymmetric_stop_protection():
    """Verify safety state transitions and that stop loss orders ALWAYS execute even when signals paused."""
    # Setup simulated portfolio, broker, and risk manager
    portfolio = Portfolio(initial_cash=100_000.0, allow_shorting=False)
    broker = SimulatedBroker()
    risk_mgr = RiskManager(max_position_pct=0.50, max_drawdown_limit=0.50)
    order_mgr = PaperOrderManager(session_id="test_safety_session")

    # Create session in SIGNALS_PAUSED state
    session = PaperTradingSession(
        session_id="test_safety_session",
        dataset_id="AAPL",
        symbols=["AAPL"],
        strategy="TimeSeriesMomentum",
        mode=SessionMode.REAL_TIME.value,
        safety_state=SignalSafetyState.SIGNALS_PAUSED.value,
        initial_capital=100_000.0,
    )
    assert session.safety_state == SignalSafetyState.SIGNALS_PAUSED.value

    # Simulate an existing open long position with a protective stop-loss
    t_open = datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
    entry_order = Order(
        order_id="entry_1",
        symbol="AAPL",
        order_type=OrderType.MARKET,
        side=OrderSide.BUY,
        quantity=100.0,
        created_at=t_open,
    )
    fill = broker.execute_market_order(
        entry_order,
        OHLCVBar(timestamp=t_open, open=150.0, high=151.0, low=149.0, close=150.0, volume=1000.0, symbol="AAPL"),
    )
    portfolio.update_fill(fill)
    risk_mgr.set_position_stop("AAPL", 140.0)

    # Place stop order in broker
    stop_order = Order(
        order_id="stop_1",
        symbol="AAPL",
        order_type=OrderType.STOP_LOSS,
        side=OrderSide.SELL,
        quantity=100.0,
        stop_price=140.0,
        created_at=t_open,
    )
    broker.submit_order(stop_order)

    # Now verify: data feed becomes STALE -> session is SIGNALS_PAUSED
    session.safety_state = SignalSafetyState.SIGNALS_PAUSED.value

    # Gap down occurs (e.g. price drops to 135.0)
    t_crash = t_open + timedelta(minutes=1)
    crash_bar = OHLCVBar(
        timestamp=t_crash,
        open=138.0,
        high=139.0,
        low=134.0,
        close=135.0,
        volume=5000.0,
        symbol="AAPL",
    )

    # Invariant: Broker processes stops regardless of session.safety_state!
    executed_stops = broker.process_pending_orders(crash_bar)
    assert len(executed_stops) == 1
    stop_fill = executed_stops[0]
    assert stop_fill.order.order_type == OrderType.STOP_LOSS
    assert stop_fill.quantity == 100.0
    # Stop executed safely at gap price
    assert stop_fill.fill_price <= 140.0

    portfolio.update_fill(stop_fill)
    pos = portfolio.get_position("AAPL")
    assert pos.quantity == 0.0  # Position protected and fully closed
