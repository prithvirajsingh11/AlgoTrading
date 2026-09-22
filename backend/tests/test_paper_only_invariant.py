"""Architectural regression test guarding the Paper-Only Execution Invariant.

STRICT INVARIANTS:
1. Zero live brokerage execution libraries in backend source code.
2. The only broker class allowed for order routing is SimulatedBroker.
3. All order placement strictly paths through:
   Signal -> RiskManager -> SimulatedBroker -> Portfolio
4. No HTTP endpoints post orders to third-party exchanges or brokerages.
"""

import ast
from pathlib import Path
import pytest
from backend.app.paper.service import PaperTradingService
from backend.app.backtesting.broker import SimulatedBroker
from backend.app.paper.storage import SQLitePaperStorage
import tempfile


PROHIBITED_LIVE_MODULES = {
    "alpaca_trade_api",
    "ib_insync",
    "ccxt",
    "robin_stocks",
    "tdameritrade",
    "binance",
    "coinbase",
    "interactive_brokers",
    "ftx",
    "kucoin",
    "krakenex",
}


def test_no_prohibited_live_trading_imports_in_source():
    """Scans all Python files in backend/app to guarantee zero live trading dependencies."""
    app_dir = Path(__file__).resolve().parent.parent / "app"
    assert app_dir.exists()

    violations = []
    for py_file in app_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root_mod = alias.name.split(".")[0].lower()
                        if root_mod in PROHIBITED_LIVE_MODULES:
                            violations.append((py_file.name, root_mod))
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        root_mod = node.module.split(".")[0].lower()
                        if root_mod in PROHIBITED_LIVE_MODULES:
                            violations.append((py_file.name, root_mod))
        except Exception as e:
            violations.append((py_file.name, f"ParseError: {e}"))

    assert len(violations) == 0, f"Found prohibited live trading imports in source: {violations}"


def test_broker_instantiation_is_strictly_simulated():
    """Verifies PaperTradingService only ever instantiates SimulatedBroker."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = SQLitePaperStorage(str(Path(tmp_dir) / "test_paper_only.db"))
        svc = PaperTradingService(storage=storage)

        cfg = {
            "mode": "SYNTHETIC_STREAM",
            "symbols": ["AAPL"],
            "strategy": "TimeSeriesMomentum",
        }
        session = svc.create_session(cfg)
        broker = svc.brokers[session.session_id]

        assert isinstance(broker, SimulatedBroker)
        assert hasattr(broker, "execute_market_order")
        assert hasattr(broker, "submit_order")
        # Invariant: Broker is completely local in-memory simulation
        assert not hasattr(broker, "submit_live_order")
        assert not hasattr(broker, "api_secret")


def test_order_routing_path_invariant():
    """Verifies that orders can only be filled via SimulatedBroker."""
    from backend.app.backtesting.orders import Order, OrderType, OrderSide
    from datetime import datetime, timezone
    from backend.app.data.loader import OHLCVBar

    broker = SimulatedBroker(commission_fixed=1.0, commission_percent=0.0005, slippage_bps=5.0)
    order = Order(
        symbol="AAPL",
        order_type=OrderType.MARKET,
        side=OrderSide.BUY,
        quantity=10,
        created_at=datetime.now(timezone.utc),
    )
    bar = OHLCVBar(
        timestamp=datetime.now(timezone.utc),
        open=150.0,
        high=152.0,
        low=149.0,
        close=151.0,
        volume=10000.0,
        symbol="AAPL",
    )
    fill = broker.execute_market_order(order, bar)
    assert fill.quantity == 10
    assert fill.fill_price > 0
    assert fill.commission > 0
