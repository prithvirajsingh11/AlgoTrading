import pytest
from datetime import datetime
from backend.app.backtesting.orders import (
    Order,
    OrderType,
    OrderSide,
    OrderStatus,
    ExecutionResult,
)
from backend.app.backtesting.portfolio import Portfolio


def test_portfolio_buy_and_sell_accounting():
    portfolio = Portfolio(initial_cash=10_000.0)
    dt1 = datetime(2023, 1, 1, 10, 0)

    # 1. Buy 50 shares at $100 with $2 commission and $0.50 slippage
    buy_order = Order(symbol="AAPL", order_type=OrderType.MARKET, side=OrderSide.BUY, quantity=50.0, created_at=dt1)
    exec1 = ExecutionResult(order=buy_order, fill_price=100.0, commission=2.0, slippage=0.50, timestamp=dt1)
    portfolio.update_fill(exec1)

    # Cash should be: 10000 - (50 * 100 + 2) = 4998.0
    assert portfolio.cash == 4998.0
    pos = portfolio.get_position("AAPL")
    assert pos.quantity == 50.0
    assert pos.avg_entry_price == 100.0

    # 2. Mark to market at $110
    dt2 = datetime(2023, 1, 2, 10, 0)
    pt = portfolio.mark_to_market(dt2, {"AAPL": 110.0})
    # Positions value: 50 * 110 = 5500.0
    # Total equity: 4998 + 5500 = 10498.0
    # Unrealized P&L: 50 * (110 - 100) = 500.0
    assert pt.positions_value == 5500.0
    assert pt.total_equity == 10498.0
    assert pt.unrealized_pnl == 500.0

    # 3. Sell 50 shares at $110 with $2 commission and $0.50 slippage
    sell_order = Order(symbol="AAPL", order_type=OrderType.MARKET, side=OrderSide.SELL, quantity=50.0, created_at=dt2)
    exec2 = ExecutionResult(order=sell_order, fill_price=110.0, commission=2.0, slippage=0.50, timestamp=dt2)
    trade = portfolio.update_fill(exec2)

    # Net revenue from sale: 50 * 110 - 2 = 5498.0
    # Final cash: 4998 + 5498 = 10496.0
    assert portfolio.cash == 10496.0
    assert pos.quantity == 0.0
    assert pos.avg_entry_price == 0.0

    # Realized P&L on trade: (110 - 100) * 50 - 2 - 0.50 = 497.50
    assert trade is not None
    assert trade.pnl == 497.50
    assert portfolio.cumulative_realized_pnl == 497.50


def test_portfolio_rejects_overselling():
    portfolio = Portfolio(initial_cash=1000.0)
    dt = datetime(2023, 1, 1, 10, 0)
    sell_order = Order(symbol="AAPL", order_type=OrderType.MARKET, side=OrderSide.SELL, quantity=10.0, created_at=dt)
    exec_sell = ExecutionResult(order=sell_order, fill_price=100.0, commission=1.0, slippage=0.0, timestamp=dt)

    with pytest.raises(ValueError, match="Attempted to sell 10.0 shares of AAPL, but only 0.0 held"):
        portfolio.update_fill(exec_sell)
