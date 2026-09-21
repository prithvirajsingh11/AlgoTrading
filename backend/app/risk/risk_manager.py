from typing import Optional, Tuple, Dict, List
from datetime import datetime
from backend.app.backtesting.orders import Order, OrderSide, OrderType
from backend.app.backtesting.portfolio import Portfolio


class RiskManager:
    """Validates pre-trade risk constraints, balance adequacy, and drawdown limits."""

    def __init__(
        self,
        max_position_pct: float = 0.50,
        max_drawdown_limit: float = 0.30,
        allow_shorting: bool = False,
    ):
        """
        max_position_pct: Maximum portfolio fraction permitted in a single asset.
        max_drawdown_limit: Peak-to-trough drawdown threshold triggering trading halt.
        allow_shorting: Whether opening short positions is permitted.
        """
        self.max_position_pct = max_position_pct
        self.max_drawdown_limit = max_drawdown_limit
        self.allow_shorting = allow_shorting
        self._peak_equity: float = 0.0
        self.position_stops: Dict[str, float] = {}

    def update_peak_equity(self, current_equity: float) -> None:
        if current_equity > self._peak_equity:
            self._peak_equity = current_equity

    def is_drawdown_halted(self, current_equity: float) -> bool:
        if self._peak_equity <= 0:
            return False
        drawdown = (self._peak_equity - current_equity) / self._peak_equity
        return drawdown >= self.max_drawdown_limit

    def set_position_stop(self, symbol: str, stop_price: float) -> None:
        """Sets a protective stop-loss price for an active symbol position."""
        if stop_price <= 0:
            raise ValueError("Stop loss price must be positive.")
        self.position_stops[symbol] = stop_price

    def get_position_stop(self, symbol: str) -> Optional[float]:
        return self.position_stops.get(symbol)

    def clear_position_stop(self, symbol: str) -> None:
        self.position_stops.pop(symbol, None)

    def check_position_stops(
        self,
        portfolio: Portfolio,
        current_prices: Dict[str, float],
        timestamp: datetime,
    ) -> List[Order]:
        """Checks if current market prices have breached any active stop-loss thresholds."""
        stop_orders: List[Order] = []
        triggered_symbols: List[str] = []

        for symbol, stop_price in self.position_stops.items():
            pos = portfolio.get_position(symbol)
            if pos.quantity > 0 and symbol in current_prices:
                price = current_prices[symbol]
                if price <= stop_price:
                    order = Order(
                        symbol=symbol,
                        order_type=OrderType.MARKET,
                        side=OrderSide.SELL,
                        quantity=pos.quantity,
                        created_at=timestamp,
                    )
                    valid, _ = self.validate_order(order, price, portfolio)
                    if valid:
                        stop_orders.append(order)
                        triggered_symbols.append(symbol)

        for sym in triggered_symbols:
            self.clear_position_stop(sym)

        return stop_orders

    def validate_order(
        self,
        order: Order,
        current_price: float,
        portfolio: Portfolio,
    ) -> Tuple[bool, Optional[str]]:
        current_equity = portfolio.get_total_equity({order.symbol: current_price})
        self.update_peak_equity(current_equity)

        # 1. Circuit breaker check
        if self.is_drawdown_halted(current_equity):
            return False, f"Trading halted: Drawdown exceeded circuit breaker limit ({self.max_drawdown_limit:.1%})"

        pos = portfolio.get_position(order.symbol)

        # 2. Stop-loss order specific validations
        if order.order_type == OrderType.STOP_LOSS:
            if order.stop_price is None or order.stop_price <= 0:
                return False, "Stop-loss order requires a positive stop_price."
            if order.side == OrderSide.SELL and order.stop_price >= current_price:
                return False, f"Stop-loss sell price (${order.stop_price:.2f}) must be below current price (${current_price:.2f})."
            if order.side == OrderSide.BUY and order.stop_price <= current_price:
                return False, f"Stop-loss buy price (${order.stop_price:.2f}) must be above current price (${current_price:.2f})."

        if order.side == OrderSide.BUY:
            # 3. Cash sufficiency check
            estimated_cost = order.quantity * current_price
            if estimated_cost > portfolio.cash:
                return False, f"Insufficient cash: Required ~${estimated_cost:.2f}, available ${portfolio.cash:.2f}"

            # 4. Position concentration limit
            post_trade_value = (pos.quantity + order.quantity) * current_price
            if current_equity > 0 and (post_trade_value / current_equity) > (self.max_position_pct + 1e-4):
                return False, f"Concentration limit exceeded: target {post_trade_value / current_equity:.1%} > max {self.max_position_pct:.1%}"

        elif order.side == OrderSide.SELL:
            # 5. Long-only constraint check
            if not self.allow_shorting:
                if pos.quantity < order.quantity:
                    return False, f"Shorting not permitted: held {pos.quantity} shares, tried to sell {order.quantity}"

        return True, None
