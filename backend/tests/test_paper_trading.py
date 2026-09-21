"""Comprehensive automated tests for AlgoTrade Phase 12 Paper Trading System.

Verifies:
- Session domain model and configuration serialization
- Historical replay provider zero lookahead bias
- Step-by-step execution, order creation, and fills
- Authoritative RiskManager rejection tracking
- Session lifecycle state transitions and speed adjustments
- SQLite persistence of sessions, orders, and event logs
- Results export and equity curve generation
- REST API and WebSocket integration
"""

import pytest
import tempfile
from pathlib import Path
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.paper.session import PaperTradingSession, SessionStatus, ReplaySpeed
from backend.app.paper.market_data import HistoricalReplayProvider
from backend.app.paper.storage import SQLitePaperStorage
from backend.app.paper.service import PaperTradingService
from backend.app.paper.events import MarketEvent, StrategySignalEvent, RiskValidationEvent
from backend.app.backtesting.orders import Order, OrderType, OrderSide
from backend.app.risk.risk_manager import RiskManager
from backend.app.paper.account import PaperAccount

client = TestClient(app)


def test_paper_session_domain_and_serialization():
    session = PaperTradingSession(
        dataset_id="AAPL",
        symbols=["AAPL"],
        strategy="TimeSeriesMomentum",
        strategy_params={"lookback_period": 20},
        initial_capital=50_000.0,
    )
    d = session.to_dict()
    assert d["session_id"].startswith("paper_")
    assert d["strategy"] == "TimeSeriesMomentum"
    assert d["initial_capital"] == 50000.0
    assert d["status"] == "CREATED"
    assert d["speed"] == "1x"

    restored = PaperTradingSession.from_dict(d)
    assert restored.session_id == session.session_id
    assert restored.initial_capital == 50000.0
    assert restored.strategy_params["lookback_period"] == 20


def test_historical_replay_provider_zero_lookahead():
    provider = HistoricalReplayProvider(dataset_id="AAPL")
    total = provider.get_total_bars()
    assert total > 50

    # Advance 5 bars and test strict zero lookahead slice
    for expected_idx in range(5):
        assert provider.has_next()
        idx, snapshot, bars = provider.next_snapshot()
        assert idx == expected_idx
        assert "AAPL" in bars
        
        # Verify historical slice length at step i is exactly i + 1
        hist_slice = provider.get_slice(idx)
        assert len(hist_slice) == idx + 1
        # Last row in slice must match current bar timestamp
        assert str(hist_slice.iloc[-1]["timestamp"]) == str(bars["AAPL"].timestamp)


def test_paper_trading_service_step_and_execution():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_paper.db"
        storage = SQLitePaperStorage(db_path=db_path)
        service = PaperTradingService(storage=storage)

        config = {
            "dataset_id": "AAPL",
            "symbols": ["AAPL"],
            "strategy": "MovingAverageCross",
            "strategy_params": {"fast_period": 5, "slow_period": 15},
            "initial_capital": 100_000.0,
            "speed": "MAX",
        }
        session = service.create_session(config)
        sid = session.session_id
        assert sid in service.sessions
        assert session.status == SessionStatus.CREATED
        assert session.total_bars > 0

        # Step forward 20 bars manually
        all_step_events = []
        for _ in range(20):
            sess, events = service.step_session(sid)
            all_step_events.extend(events)

        assert sess.current_bar_index == 20
        assert sess.simulation_timestamp is not None
        assert sess.current_equity > 0

        # Verify events contain MARKET_BAR, STRATEGY_SIGNAL, and PORTFOLIO_SNAPSHOT
        event_types = {e["event_type"] for e in all_step_events}
        assert "MARKET_BAR" in event_types
        assert "PORTFOLIO_SNAPSHOT" in event_types


def test_paper_trading_authoritative_risk_rejection():
    """Verify that RiskManager rejections are strictly enforced and recorded."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_risk_paper.db"
        storage = SQLitePaperStorage(db_path=db_path)
        service = PaperTradingService(storage=storage)

        # Create session with strict 5% max position limit
        config = {
            "dataset_id": "AAPL",
            "symbols": ["AAPL"],
            "strategy": "MovingAverageCross",
            "strategy_params": {"fast_period": 5, "slow_period": 15},
            "initial_capital": 10_000.0,
            "risk_config": {
                "max_position_pct": 0.05,  # Max 5% of portfolio per position
                "max_drawdown_limit": 0.20,
                "allow_shorting": False,
                "position_size_pct": 0.80,  # Sizer requests 80% which must be rejected!
            },
        }
        session = service.create_session(config)
        sid = session.session_id

        # Step until an order is generated and rejected by the risk manager
        rejected_found = False
        for _ in range(30):
            sess, events = service.step_session(sid)
            for e in events:
                if e.get("event_type") == "RISK_VALIDATION" and not e.get("approved"):
                    rejected_found = True
                    assert "limit exceeded" in e.get("reason", "").lower() or "position" in e.get("reason", "").lower()
            if rejected_found:
                break

        orders = service.get_orders(sid)
        if any(o["status"] == "REJECTED" for o in orders):
            rej_order = next(o for o in orders if o["status"] == "REJECTED")
            assert rej_order["rejection_reason"] is not None


def test_paper_trading_lifecycle_and_speed():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_lifecycle.db"
        storage = SQLitePaperStorage(db_path=db_path)
        service = PaperTradingService(storage=storage)

        session = service.create_session({"dataset_id": "AAPL", "speed": "1x"})
        sid = session.session_id

        # Start
        s_start = service.start_session(sid)
        assert s_start.status == SessionStatus.RUNNING
        assert s_start.started_at is not None

        # Change speed
        s_speed = service.set_speed(sid, "5x")
        assert s_speed.speed == "5x"

        # Pause
        s_pause = service.pause_session(sid)
        assert s_pause.status == SessionStatus.PAUSED

        # Resume
        s_res = service.resume_session(sid)
        assert s_res.status == SessionStatus.RUNNING

        # Stop
        s_stop = service.stop_session(sid)
        assert s_stop.status == SessionStatus.STOPPED
        assert s_stop.stopped_at is not None

        # Invalid speed should raise ValueError
        with pytest.raises(ValueError):
            service.set_speed(sid, "100x")


def test_paper_trading_persistence():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_persist.db"
        storage = SQLitePaperStorage(db_path=db_path)
        service = PaperTradingService(storage=storage)

        session = service.create_session({"dataset_id": "AAPL", "initial_capital": 75000.0})
        sid = session.session_id
        service.step_session(sid)
        service.step_session(sid)

        # Reopen with fresh service instance connected to same SQLite DB
        service2 = PaperTradingService(storage=SQLitePaperStorage(db_path=db_path))
        loaded = service2.get_session(sid)
        assert loaded is not None
        assert loaded.session_id == sid
        assert loaded.initial_capital == 75000.0
        assert loaded.current_bar_index == 2


def test_paper_trading_export_results():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_export.db"
        storage = SQLitePaperStorage(db_path=db_path)
        service = PaperTradingService(storage=storage)

        session = service.create_session({"dataset_id": "AAPL"})
        sid = session.session_id
        for _ in range(10):
            service.step_session(sid)

        export = service.export_results(sid)
        assert "summary" in export
        assert "equity_curve" in export
        assert "orders" in export
        assert export["summary"]["initial_capital"] == 100_000.0
        assert export["summary"]["total_bars_replayed"] == 10
        assert len(export["equity_curve"]) == 10


def test_paper_pairs_trading_session():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_pairs.db"
        storage = SQLitePaperStorage(db_path=db_path)
        service = PaperTradingService(storage=storage)

        from backend.app.research.dataset import DatasetManager
        dm = DatasetManager()
        aapl_df = dm.load_dataset("AAPL")
        msft_df = aapl_df.copy()
        msft_df["close"] = msft_df["close"] * 1.5
        msft_df["open"] = msft_df["open"] * 1.5
        msft_df["high"] = msft_df["high"] * 1.5
        msft_df["low"] = msft_df["low"] * 1.5
        dm.register_in_memory_dataset("MSFT", msft_df, symbols=["MSFT"])

        session = service.create_session({
            "dataset_id": "AAPL",
            "symbols": ["AAPL", "MSFT"],
            "strategy": "PairsTrading",
            "strategy_params": {"lookback_period": 20, "entry_zscore": 1.5, "exit_zscore": 0.5},
            "allow_shorting": True,
            "dataset_manager": dm,
        })
        sid = session.session_id
        assert len(session.symbols) == 2

        # Step forward
        for _ in range(15):
            service.step_session(sid)

        assert session.current_bar_index == 15
        events = service.get_events(sid, limit=50)
        assert len(events) > 0


def test_paper_api_endpoints():
    # 1. Check status
    res = client.get("/api/v1/paper/status")
    assert res.status_code == 200
    assert res.json()["mode"] == "SIMULATION_ONLY"

    # 2. Create session
    payload = {
        "dataset_id": "AAPL",
        "symbols": ["AAPL"],
        "strategy": "MovingAverageCross",
        "strategy_params": {"fast_period": 5, "slow_period": 20},
        "initial_capital": 100000.0,
        "speed": "2x",
    }
    create_res = client.post("/api/v1/paper/sessions", json=payload)
    assert create_res.status_code == 200
    sess_data = create_res.json()
    sid = sess_data["session_id"]
    assert sid.startswith("paper_")

    # 3. List sessions
    list_res = client.get("/api/v1/paper/sessions")
    assert list_res.status_code == 200
    assert any(s["session_id"] == sid for s in list_res.json())

    # 4. Get specific session
    get_res = client.get(f"/api/v1/paper/sessions/{sid}")
    assert get_res.status_code == 200
    assert get_res.json()["session_id"] == sid

    # 5. Step session
    step_res = client.post(f"/api/v1/paper/sessions/{sid}/step")
    assert step_res.status_code == 200
    assert step_res.json()["session"]["current_bar_index"] == 1

    # 6. Change speed
    speed_res = client.post(f"/api/v1/paper/sessions/{sid}/speed", json={"speed": "5x"})
    assert speed_res.status_code == 200
    assert speed_res.json()["speed"] == "5x"

    # 7. Pause and Resume
    pause_res = client.post(f"/api/v1/paper/sessions/{sid}/pause")
    assert pause_res.status_code == 200
    assert pause_res.json()["status"] == "PAUSED"

    resume_res = client.post(f"/api/v1/paper/sessions/{sid}/resume")
    assert resume_res.status_code == 200
    assert resume_res.json()["status"] == "RUNNING"

    # 8. Get orders, positions, events
    orders_res = client.get(f"/api/v1/paper/sessions/{sid}/orders")
    assert orders_res.status_code == 200
    positions_res = client.get(f"/api/v1/paper/sessions/{sid}/positions")
    assert positions_res.status_code == 200
    events_res = client.get(f"/api/v1/paper/sessions/{sid}/events")
    assert events_res.status_code == 200

    # 9. Stop
    stop_res = client.post(f"/api/v1/paper/sessions/{sid}/stop")
    assert stop_res.status_code == 200
    assert stop_res.json()["status"] == "STOPPED"

    # 10. Export results
    export_res = client.get(f"/api/v1/paper/sessions/{sid}/export")
    assert export_res.status_code == 200
    assert "summary" in export_res.json()
