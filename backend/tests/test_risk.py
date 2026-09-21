from datetime import datetime
from backend.app.backtesting.orders import Order, OrderType, OrderSide
from backend.app.backtesting.portfolio import Portfolio
from backend.app.risk.position_sizing import FixedQuantitySizer, PercentEquitySizer
from backend.app.risk.risk_manager import RiskManager


def test_position_sizers():
    portfolio = Portfolio(initial_cash=100_000.0)

    fixed_sizer = FixedQuantitySizer(quantity=25.0)
    assert fixed_sizer.calculate_quantity("AAPL", 150.0, portfolio) == 25.0

    # 10% of 100,000 = $10,000. At $200/share -> 50 shares
    pct_sizer = PercentEquitySizer(percent_equity=0.10)
    assert pct_sizer.calculate_quantity("AAPL", 200.0, portfolio) == 50.0


def test_risk_manager_cash_check():
    portfolio = Portfolio(initial_cash=1_000.0)
    risk_manager = RiskManager(max_position_pct=1.0)
    dt = datetime(2023, 1, 1, 10, 0)

    # Requires $1500, but only $1000 cash available
    order = Order(symbol="AAPL", order_type=OrderType.MARKET, side=OrderSide.BUY, quantity=10.0, created_at=dt)
    valid, reason = risk_manager.validate_order(order, current_price=150.0, portfolio=portfolio)
    assert not valid
    assert "Insufficient cash" in reason


def test_risk_manager_shorting_check():
    portfolio = Portfolio(initial_cash=100_000.0)
    risk_manager = RiskManager(allow_shorting=False)
    dt = datetime(2023, 1, 1, 10, 0)

    # Tried to sell with 0 position
    order = Order(symbol="AAPL", order_type=OrderType.MARKET, side=OrderSide.SELL, quantity=10.0, created_at=dt)
    valid, reason = risk_manager.validate_order(order, current_price=150.0, portfolio=portfolio)
    assert not valid
    assert "Shorting not permitted" in reason


def test_risk_manager_concentration_limit():
    portfolio = Portfolio(initial_cash=100_000.0)
    # Max position allowed: 30% of portfolio
    risk_manager = RiskManager(max_position_pct=0.30)
    dt = datetime(2023, 1, 1, 10, 0)

    # 400 shares * $100 = $40,000 (40% of portfolio) -> exceeds 30%
    order = Order(symbol="AAPL", order_type=OrderType.MARKET, side=OrderSide.BUY, quantity=400.0, created_at=dt)
    valid, reason = risk_manager.validate_order(order, current_price=100.0, portfolio=portfolio)
    assert not valid
    assert "Concentration limit exceeded" in reason


def test_risk_manager_circuit_breaker():
    portfolio = Portfolio(initial_cash=100_000.0)
    risk_manager = RiskManager(max_drawdown_limit=0.20)
    dt = datetime(2023, 1, 1, 10, 0)

    # Simulate portfolio peaking at 100,000, then dropping to 75,000 (25% drawdown > 20% limit)
    risk_manager.update_peak_equity(100_000.0)
    portfolio.cash = 75_000.0

    order = Order(symbol="AAPL", order_type=OrderType.MARKET, side=OrderSide.BUY, quantity=10.0, created_at=dt)
    valid, reason = risk_manager.validate_order(order, current_price=100.0, portfolio=portfolio)
    assert not valid
    assert "Drawdown exceeded circuit breaker" in reason
