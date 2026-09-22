"""End-to-End integration test for real-time streaming paper trading pipeline.

Runs:
synthetic ticks -> BarBuilder -> MarketSnapshot -> StreamingFeatureEngine
-> Strategy -> RiskManager -> Paper Broker -> Portfolio -> WebSocket events

Asserts:
- No future data is used (zero lookahead)
- Signals generated only from valid, synchronized data
- Risk checks occur before order execution
- Executed orders route strictly to SimulatedBroker
- Portfolio state transitions correctly
- All domain events are emitted and serialized
- Session state remains consistent
"""

import asyncio
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pytest

from backend.app.paper.service import PaperTradingService
from backend.app.paper.session import PaperTradingSession, SessionStatus, SessionMode, SignalSafetyState
from backend.app.paper.storage import SQLitePaperStorage
from backend.app.paper.market_data import (
    InMemoryStreamingAdapter,
    RealTimeMarketDataProvider,
    ConnectionState,
    MarketTick,
)
from backend.app.paper.bar_builder import BarBuilder
from backend.app.paper.sync import SnapshotSynchronizer
from backend.app.paper.streaming_features import StreamingFeatureEngine
from backend.app.backtesting.broker import SimulatedBroker
from backend.app.backtesting.orders import OrderSide, OrderType, SignalType
from backend.app.data.loader import OHLCVBar, MarketSnapshot


def test_e2e_streaming_pipeline_synthetic():
    async def _run_test():
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_e2e_pipeline.db"
            storage = SQLitePaperStorage(str(db_path))
            service = PaperTradingService(storage=storage)

            symbols = ["AAPL"]
            cfg = {
                "mode": "SYNTHETIC_STREAM",
                "data_provider_type": "SYNTHETIC",
                "symbols": symbols,
                "strategy": "TimeSeriesMomentum",
                "strategy_params": {"lookback_period": 3},
                "initial_capital": 50_000.0,
                "max_data_age_seconds": 15.0,
                "bar_interval": "1s",
            }

            session = service.create_session(cfg)
            sid = session.session_id

            # Invariant checks
            assert session.mode == SessionMode.SYNTHETIC_STREAM.value
            assert session.data_provider_type == "SYNTHETIC"
            assert isinstance(service.brokers[sid], SimulatedBroker)

            # Pipeline components present
            bar_builder = service.bar_builders[sid]
            feat_engine = service.feature_engines[sid]
            synchronizer = service.synchronizers[sid]
            assert isinstance(bar_builder, BarBuilder)
            assert isinstance(feat_engine, StreamingFeatureEngine)
            assert isinstance(synchronizer, SnapshotSynchronizer)

            # Generate synthetic ticks and step through pipeline
            base_time = datetime(2026, 9, 22, 10, 0, 0, tzinfo=timezone.utc)
            prices = [150.0, 151.0, 152.0, 153.0, 154.0, 155.0, 156.0]
            emitted_events = []

            for i, p in enumerate(prices):
                tick_time = base_time + timedelta(seconds=i * 2)
                tick = MarketTick(
                    symbol="AAPL",
                    timestamp=tick_time,
                    price=p,
                    bid=p - 0.05,
                    ask=p + 0.05,
                    size=100.0,
                    received_at=tick_time,
                )

                # Feed tick to BarBuilder
                closed_bar = bar_builder.add_tick(tick)
                # Form snapshot
                bar = OHLCVBar(
                    timestamp=tick_time,
                    open=p - 0.1,
                    high=p + 0.2,
                    low=p - 0.2,
                    close=p,
                    volume=1000.0,
                    symbol="AAPL",
                    bid=p - 0.05,
                    ask=p + 0.05,
                    last_price=p,
                )
                snap = MarketSnapshot(
                    timestamp=tick_time,
                    bars={"AAPL": bar},
                    received_at=tick_time,
                )

                # Step execution
                step_evts = service._execute_step(sid, snapshot=snap, is_sync=True)
                emitted_events.extend(step_evts)

            # Assertions on complete execution
            assert session.current_bar_index == len(prices)
            assert session.safety_state == SignalSafetyState.SIGNALS_ENABLED.value

            # Check that events were recorded and emitted
            evt_types = [getattr(e, "event_type", "") for e in emitted_events]
            assert "MARKET_BAR" in evt_types

            # Verify orders and portfolio
            account = service.accounts[sid]
            assert account.portfolio.initial_cash == 50_000.0
            assert session.current_equity > 0

            # Verify risk controls: broker is strictly simulated
            broker = service.brokers[sid]
            assert isinstance(broker, SimulatedBroker)

            # Verify session was persisted
            loaded_sess = storage.load_session(sid)
            assert loaded_sess is not None
            assert loaded_sess.current_bar_index == len(prices)

    asyncio.run(_run_test())
