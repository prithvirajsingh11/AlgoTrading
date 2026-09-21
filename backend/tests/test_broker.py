from datetime import datetime
from backend.app.data.loader import OHLCVBar
from backend.app.backtesting.orders import (
    Order,
    OrderType,
    OrderSide,
    OrderStatus,
)
from backend.app.backtesting.broker import SimulatedBroker


def test_market_order_execution_and_slippage():
    broker = SimulatedBroker(commission_fixed=2.0, commission_percent=0.001, slippage_bps=10.0)
    dt = datetime(2023, 1, 1, 10, 0)
    bar = OHLCVBar(timestamp=dt, open=100.0, high=105.0, low=99.0, close=100.0, volume=1000)

    # BUY order: fill price should experience upward slippage (10 bps = 0.1%) -> 100 * 1.001 = 100.10
    buy_order = Order(symbol="AAPL", order_type=OrderType.MARKET, side=OrderSide.BUY, quantity=10.0, created_at=dt)
    execution = broker.execute_market_order(buy_order, bar)

    assert buy_order.status == OrderStatus.FILLED
    assert pytest_approx(execution.fill_price, 100.10)
    # Commission: 2.0 fixed + 10 * 100.10 * 0.001 = 2.0 + 1.001 = 3.001
    assert pytest_approx(execution.commission, 3.001)

    # SELL order: fill price should experience downward slippage -> 100 * 0.999 = 99.90
    sell_order = Order(symbol="AAPL", order_type=OrderType.MARKET, side=OrderSide.SELL, quantity=10.0, created_at=dt)
    sell_exec = broker.execute_market_order(sell_order, bar)
    assert pytest_approx(sell_exec.fill_price, 99.90)


def test_limit_order_execution():
    broker = SimulatedBroker(commission_fixed=0.0, commission_percent=0.0, slippage_bps=0.0)
    dt = datetime(2023, 1, 1, 10, 0)
    bar = OHLCVBar(timestamp=dt, open=102.0, high=105.0, low=98.0, close=101.0, volume=1000)

    # Limit BUY at 99.0 triggers because bar.low (98.0) <= 99.0
    limit_buy = Order(symbol="AAPL", order_type=OrderType.LIMIT, side=OrderSide.BUY, quantity=5.0, limit_price=99.0, created_at=dt)
    broker.submit_order(limit_buy)

    # Limit SELL at 110.0 should NOT trigger because bar.high (105.0) < 110.0
    limit_sell = Order(symbol="AAPL", order_type=OrderType.LIMIT, side=OrderSide.SELL, quantity=5.0, limit_price=110.0, created_at=dt)
    broker.submit_order(limit_sell)

    fills = broker.process_pending_orders(bar)
    assert len(fills) == 1
    assert fills[0].order.order_id == limit_buy.order_id
    assert fills[0].fill_price <= 99.0
    assert len(broker.pending_orders) == 1
    assert broker.pending_orders[0].order_id == limit_sell.order_id


def pytest_approx(a, b, tol=1e-4):
    return abs(a - b) < tol
