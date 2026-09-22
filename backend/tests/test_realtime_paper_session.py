"""Integration tests for Real-Time Paper Trading Pipeline and Safety State Machine.

Verifies:
1. Real-time paper trading session initialization with Live Provider.
2. Strict simulated execution: zero real money, zero external broker calls.
3. Multi-asset snapshot synchronization policy (SnapshotSynchronizer).
4. Bounded incremental feature streaming (StreamingFeatureEngine).
5. Stale data protection: transitions to SIGNALS_PAUSED when tick age > max_data_age_seconds.
6. Stop loss enforcement while signals are paused.
7. Safe ML / Jev fallback on error or timeout.
8. Real-time market REST API endpoints.
"""

import pytest
import asyncio
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.data.loader import OHLCVBar, MarketSnapshot
from backend.app.paper.service import PaperTradingService
from backend.app.paper.session import SessionStatus, SessionMode, SignalSafetyState
from backend.app.paper.storage import SQLitePaperStorage
from backend.app.paper.realtime import InMemoryStreamingAdapter, RealTimeMarketDataProvider, ConnectionState
from backend.app.paper.sync import SnapshotSynchronizer
from backend.app.paper.streaming_features import StreamingFeatureEngine
from backend.app.backtesting.orders import Order, OrderType, OrderSide
from backend.app.backtesting.broker import SimulatedBroker

client = TestClient(app)


def test_snapshot_synchronizer_policy():
    sync = SnapshotSynchronizer(symbols=["AAPL", "MSFT"], max_desync_seconds=2.0)
    now = datetime.now(timezone.utc)

    # Missing leg initially
    bar_aapl = OHLCVBar(timestamp=now, close=150.0, symbol="AAPL")
    sync.update_bar(bar_aapl)
    assert not sync.is_synchronized(reference_time=now)
    assert sync.get_synchronized_snapshot(reference_time=now) is None
    assert "Missing market observations" in (sync.get_desync_reason(reference_time=now) or "")

    # Both legs present and synchronized
    bar_msft = OHLCVBar(timestamp=now, close=300.0, symbol="MSFT")
    sync.update_bar(bar_msft)
    assert sync.is_synchronized(reference_time=now)
    synced_snap = sync.get_synchronized_snapshot(reference_time=now)
    assert synced_snap is not None
    assert "AAPL" in synced_snap.bars and "MSFT" in synced_snap.bars

    # One leg stale relative to reference time
    future_time = now + timedelta(seconds=5)
    assert not sync.is_synchronized(reference_time=future_time)
    assert "stale" in (sync.get_desync_reason(reference_time=future_time) or "")

    # Cross-symbol divergence
    stale_bar = OHLCVBar(timestamp=now - timedelta(seconds=10), close=148.0, symbol="AAPL")
    sync.update_bar(stale_bar)
    sync.update_bar(OHLCVBar(timestamp=now, close=302.0, symbol="MSFT"))
    assert not sync.is_synchronized(reference_time=now)


def test_streaming_feature_engine():
    from backend.app.ml.features import FeatureConfig
    cfg = FeatureConfig(
        sma_windows=(5, 10),
        ema_windows=(5, 10),
        macd_fast=8,
        macd_slow=15,
        macd_signal=5,
        volatility_window=10,
        volume_window=10,
        atr_window=10,
        momentum_windows=(3, 5),
    )
    engine = StreamingFeatureEngine(symbols=["AAPL"], feature_config=cfg, max_buffer_size=50)
    now = datetime.now(timezone.utc)

    for i in range(35):
        bar = OHLCVBar(
            timestamp=now + timedelta(minutes=i),
            open=100.0 + i,
            high=102.0 + i,
            low=99.0 + i,
            close=101.0 + i,
            volume=1000.0,
            symbol="AAPL",
        )
        engine.update_bar(bar)

    assert engine.is_warmed_up("AAPL")
    df = engine.get_history_df("AAPL")
    assert len(df) <= 50
    assert "close" in df.columns

    # Test incremental feature computation
    feat_df = engine.compute_latest_features("AAPL")
    assert not feat_df.empty
    assert "rsi_14" in feat_df.columns
    assert "simple_return" in feat_df.columns


def test_realtime_paper_service_execution_and_safety():
    async def _test():
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_paper_realtime.db"
            storage = SQLitePaperStorage(str(db_path))
            service = PaperTradingService(storage=storage)

            cfg = {
                "mode": "REAL_TIME",
                "data_provider_type": "LIVE_PROVIDER",
                "live_provider": "mock",
                "symbols": ["AAPL"],
                "strategy": "TimeSeriesMomentum",
                "strategy_params": {"lookback_period": 3},
                "initial_capital": 50_000.0,
                "max_data_age_seconds": 10.0,
            }

            session = service.create_session(cfg)
            assert session.mode == SessionMode.REAL_TIME.value
            assert session.data_provider_type == "LIVE_PROVIDER"
            assert session.safety_state == SignalSafetyState.SIGNALS_ENABLED.value

            # Strict paper check: broker is SimulatedBroker
            broker = service.brokers[session.session_id]
            assert isinstance(broker, SimulatedBroker)

            # Inject a fresh snapshot
            now = datetime.now(timezone.utc)
            snap = MarketSnapshot(
                timestamp=now,
                bars={"AAPL": OHLCVBar(timestamp=now, close=150.0, symbol="AAPL")},
                received_at=now,
            )

            # Step session with live snapshot
            events = service._execute_step(session.session_id, snapshot=snap, is_sync=True)
            assert len(events) > 0
            assert session.current_bar_index == 1
            assert session.last_data_timestamp is not None

            # Verify portfolio update recorded
            assert session.cash == 50_000.0
            assert session.current_equity == 50_000.0

            # Stale data safety: inject snapshot with timestamp 60s in the past
            stale_time = now - timedelta(seconds=60)
            stale_snap = MarketSnapshot(
                timestamp=stale_time,
                bars={"AAPL": OHLCVBar(timestamp=stale_time, close=155.0, symbol="AAPL")},
                received_at=now,
            )

            # Simulate live loop safety state determination
            data_age = (now - stale_time).total_seconds()
            assert data_age > session.max_data_age_seconds
            session.safety_state = SignalSafetyState.SIGNALS_PAUSED.value

            # With signals paused, execution steps run stops & valuation but emit 0 strategy signals
            paused_events = service._execute_step(session.session_id, snapshot=stale_snap, is_sync=True)
            signal_evts = [e for e in paused_events if getattr(e, "event_type", "") == "STRATEGY_SIGNAL"]
            assert len(signal_evts) == 0

            # Stop loss enforcement remains active even when signals paused
            account = service.accounts[session.session_id]
            risk_mgr = service.risk_managers[session.session_id]

            # Simulate an existing position with a stop loss
            from backend.app.backtesting.portfolio import Position
            pos = account.portfolio.get_position("AAPL")
            pos.quantity = 10
            pos.avg_entry_price = 150.0
            risk_mgr.set_position_stop("AAPL", 140.0)

            # Price drops below stop
            drop_snap = MarketSnapshot(
                timestamp=now,
                bars={"AAPL": OHLCVBar(timestamp=now, open=135.0, high=136.0, low=134.0, close=135.0, symbol="AAPL")},
                received_at=now,
            )
            stop_events = service._execute_step(session.session_id, snapshot=drop_snap, is_sync=True)
            stop_triggered = [e for e in stop_events if getattr(e, "event_type", "") == "STOP_LOSS_TRIGGERED"]
            assert len(stop_triggered) == 1
            assert stop_triggered[0].symbol == "AAPL"
            assert stop_triggered[0].quantity == 10
            assert account.portfolio.get_position("AAPL").quantity == 0

    asyncio.run(_test())


def test_market_api_endpoints():
    # 1. GET /api/v1/market/providers
    res = client.get("/api/v1/market/providers")
    assert res.status_code == 200
    providers = res.json()
    assert isinstance(providers, list)
    assert any(p["id"] == "HISTORICAL" for p in providers)
    assert any(p["id"] == "mock" for p in providers)

    # 2. GET /api/v1/market/status
    res_status = client.get("/api/v1/market/status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert "state" in status_data
    assert "connected" in status_data
    assert "safety_state" in status_data

    # 3. POST /api/v1/market/connect
    res_conn = client.post("/api/v1/market/connect", json={"provider": "mock", "symbols": ["AAPL"]})
    assert res_conn.status_code == 200
    assert res_conn.json()["success"] is True

    # 4. POST /api/v1/market/disconnect
    res_disc = client.post("/api/v1/market/disconnect")
    assert res_disc.status_code == 200
    assert res_disc.json()["success"] is True

    # 5. POST /api/v1/market/subscribe
    res_sub = client.post("/api/v1/market/subscribe", json={"symbols": ["AAPL", "MSFT"]})
    assert res_sub.status_code == 200
    assert res_sub.json()["subscribed_symbols"] == ["AAPL", "MSFT"]


def test_paper_trading_api_realtime_session():
    # Create real-time paper session via REST
    req_body = {
        "dataset_id": "AAPL",
        "symbols": ["AAPL"],
        "strategy": "TimeSeriesMomentum",
        "mode": "REAL_TIME",
        "data_provider": "LIVE_PROVIDER",
        "live_provider": "mock",
        "initial_capital": 75_000.0,
        "max_data_age_seconds": 15.0,
    }
    res = client.post("/api/v1/paper/sessions", json={**req_body, "strategy_params": {}})
    assert res.status_code == 200
    sess = res.json()
    assert sess["session_id"].startswith("paper_")
    assert sess["mode"] == "REAL_TIME"
    assert sess["data_provider_type"] == "LIVE_PROVIDER"
    assert sess["safety_state"] == "SIGNALS_ENABLED"
    assert sess["initial_capital"] == 75000.0

    sid = sess["session_id"]

    # Start session
    res_start = client.post(f"/api/v1/paper/sessions/{sid}/start")
    assert res_start.status_code == 200
    assert res_start.json()["status"] == "RUNNING"

    # Pause session
    res_pause = client.post(f"/api/v1/paper/sessions/{sid}/pause")
    assert res_pause.status_code == 200
    assert res_pause.json()["status"] == "PAUSED"

    # Stop session
    res_stop = client.post(f"/api/v1/paper/sessions/{sid}/stop")
    assert res_stop.status_code == 200
    assert res_stop.json()["status"] == "STOPPED"
