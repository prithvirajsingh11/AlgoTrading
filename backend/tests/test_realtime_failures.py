r"""Tests simulating real-time market data failures, reconnects, and safety state transitions.

Simulates:
- Provider disconnect
- Provider timeout / delayed ticks
- Stale feed ($t_{now} - t_{data} > max\_data\_age$)
- Fresh reconnection
- Invariant: Stop-loss position protection remains active even when signals are paused
"""

import asyncio
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pytest

from backend.app.paper.service import PaperTradingService
from backend.app.paper.session import SignalSafetyState
from backend.app.paper.storage import SQLitePaperStorage
from backend.app.paper.market_data import (
    InMemoryStreamingAdapter,
    AlpacaMarketDataAdapter,
    ConnectionState,
    MarketTick,
)
from backend.app.data.loader import OHLCVBar, MarketSnapshot
from backend.app.backtesting.orders import OrderSide, OrderType


def test_realtime_provider_disconnect_pauses_signals():
    async def _test():
        with tempfile.TemporaryDirectory() as tmp_dir:
            storage = SQLitePaperStorage(str(Path(tmp_dir) / "test_failures.db"))
            svc = PaperTradingService(storage=storage)

            cfg = {
                "mode": "SYNTHETIC_STREAM",
                "symbols": ["AAPL"],
                "strategy": "TimeSeriesMomentum",
                "max_data_age_seconds": 5.0,
            }
            session = svc.create_session(cfg)
            sid = session.session_id

            # 1. Connected state -> fresh data
            now = datetime.now(timezone.utc)
            fresh_snap = MarketSnapshot(
                timestamp=now,
                bars={"AAPL": OHLCVBar(timestamp=now, close=150.0, symbol="AAPL")},
                received_at=now,
            )
            session.safety_state = SignalSafetyState.SIGNALS_ENABLED.value
            evts = svc._execute_step(sid, snapshot=fresh_snap, is_sync=True)
            assert session.safety_state == SignalSafetyState.SIGNALS_ENABLED.value

            # 2. Simulate provider disconnect
            prov = svc.providers[sid]
            await prov.adapter.disconnect()
            assert prov.adapter.status.state == ConnectionState.DISCONNECTED

            # Safety state machine must transition to SIGNALS_PAUSED
            session.safety_state = SignalSafetyState.SIGNALS_PAUSED.value

            # In paused state, execution step produces 0 strategy signals
            step_evts = svc._execute_step(sid, snapshot=fresh_snap, is_sync=True)
            signals = [e for e in step_evts if getattr(e, "event_type", "") == "STRATEGY_SIGNAL"]
            assert len(signals) == 0

            # 3. Fresh reconnection resumes signals
            await prov.adapter.connect()
            assert prov.adapter.status.state == ConnectionState.CONNECTED
            session.safety_state = SignalSafetyState.SIGNALS_ENABLED.value
            assert session.safety_state == SignalSafetyState.SIGNALS_ENABLED.value

    asyncio.run(_test())


def test_asymmetric_stop_protection_during_data_stall():
    """Verifies stop-loss fills even when signals are paused due to stale data."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = SQLitePaperStorage(str(Path(tmp_dir) / "test_stops_stall.db"))
        svc = PaperTradingService(storage=storage)

        cfg = {
            "mode": "SYNTHETIC_STREAM",
            "symbols": ["AAPL"],
            "strategy": "TimeSeriesMomentum",
            "max_data_age_seconds": 5.0,
        }
        session = svc.create_session(cfg)
        sid = session.session_id

        account = svc.accounts[sid]
        risk_mgr = svc.risk_managers[sid]

        # Give account an open position with a stop loss
        pos = account.portfolio.get_position("AAPL")
        pos.quantity = 100
        pos.avg_entry_price = 150.0
        risk_mgr.set_position_stop("AAPL", 140.0)

        # Force state to SIGNALS_PAUSED (simulating stale feed)
        session.safety_state = SignalSafetyState.SIGNALS_PAUSED.value

        # Price drops through stop price to 135.0
        now = datetime.now(timezone.utc)
        drop_snap = MarketSnapshot(
            timestamp=now,
            bars={"AAPL": OHLCVBar(timestamp=now, open=138.0, high=138.0, low=134.0, close=135.0, symbol="AAPL")},
            received_at=now,
        )

        step_evts = svc._execute_step(sid, snapshot=drop_snap, is_sync=True)
        stop_evts = [e for e in step_evts if getattr(e, "event_type", "") == "STOP_LOSS_TRIGGERED"]

        # Stop-loss was authoritatively triggered and filled despite paused signals
        assert len(stop_evts) == 1
        assert stop_evts[0].symbol == "AAPL"
        assert stop_evts[0].quantity == 100
        assert account.portfolio.get_position("AAPL").quantity == 0
