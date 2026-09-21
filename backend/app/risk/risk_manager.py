from typing import Optional, Tuple
from backend.app.backtesting.orders import Order, OrderSide
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

    def update_peak_equity(self, current_equity: float) -> None:
        if current_equity > self._peak_equity:
            self._peak_equity = current_equity

    def is_drawdown_halted(self, current_equity: float) -> bool:
        if self._peak_equity <= 0:
            return False
        drawdown = (self._peak_equity - current_equity) / self._peak_equity
        return drawdown >= self.max_drawdown_limit

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

        if order.side == OrderSide.BUY:
            # 2. Cash sufficiency check
            estimated_cost = order.quantity * current_price
            if estimated_cost > portfolio.cash:
                return False, f"Insufficient cash: Required ~${estimated_cost:.2f}, available ${portfolio.cash:.2f}"

            # 3. Position concentration limit
            post_trade_value = (pos.quantity + order.quantity) * current_price
            if current_equity > 0 and (post_trade_value / current_equity) > (self.max_position_pct + 1e-4):
                return False, f"Concentration limit exceeded: target {post_trade_value / current_equity:.1%} > max {self.max_position_pct:.1%}"

        elif order.side == OrderSide.SELL:
            # 4. Long-only constraint check
            if not self.allow_shorting:
                if pos.quantity < order.quantity:
                    return False, f"Shorting not permitted: held {pos.quantity} shares, tried to sell {order.quantity}"

        return True, None
