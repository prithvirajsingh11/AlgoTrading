from typing import List, Optional
from datetime import datetime
from backend.app.data.loader import OHLCVBar
from backend.app.backtesting.orders import (
    Order,
    OrderType,
    OrderSide,
    OrderStatus,
    ExecutionResult,
)


class SimulatedBroker:
    """Simulates realistic broker order execution with slippage and commission fees."""

    def __init__(
        self,
        commission_fixed: float = 1.0,
        commission_percent: float = 0.0005,
        slippage_bps: float = 5.0,
    ):
        """
        commission_fixed: Fixed USD fee per filled order.
        commission_percent: Percentage fee applied to total traded value (e.g. 0.0005 = 5 bps).
        slippage_bps: Slippage in basis points (e.g. 5.0 = 0.05%).
        """
        self.commission_fixed = commission_fixed
        self.commission_percent = commission_percent
        self.slippage_bps = slippage_bps
        self.pending_orders: List[Order] = []

    def submit_order(self, order: Order) -> None:
        if order.status == OrderStatus.PENDING:
            self.pending_orders.append(order)

    def cancel_order(self, order_id: str) -> bool:
        for order in self.pending_orders:
            if order.order_id == order_id:
                order.status = OrderStatus.CANCELLED
                self.pending_orders.remove(order)
                return True
        return False

    def calculate_slippage(self, base_price: float, side: OrderSide) -> float:
        """Returns signed slippage impact per unit."""
        slip_pct = self.slippage_bps / 10_000.0
        if side == OrderSide.BUY:
            return base_price * slip_pct
        else:
            return -base_price * slip_pct

    def calculate_commission(self, traded_value: float) -> float:
        return self.commission_fixed + (traded_value * self.commission_percent)

    def execute_market_order(self, order: Order, bar: OHLCVBar) -> ExecutionResult:
        base_price = bar.close
        slip_unit = self.calculate_slippage(base_price, order.side)
        fill_price = base_price + slip_unit
        traded_value = fill_price * order.quantity
        commission = self.calculate_commission(traded_value)

        order.status = OrderStatus.FILLED
        order.filled_at = bar.timestamp
        order.filled_price = fill_price
        order.commission = commission
        order.slippage = abs(slip_unit * order.quantity)

        return ExecutionResult(
            order=order,
            fill_price=fill_price,
            commission=commission,
            slippage=order.slippage,
            timestamp=bar.timestamp,
        )

    def process_pending_orders(self, bar: OHLCVBar) -> List[ExecutionResult]:
        """Evaluates pending orders against current bar prices."""
        filled_results: List[ExecutionResult] = []
        unfilled_orders: List[Order] = []

        for order in self.pending_orders:
            if order.order_type == OrderType.MARKET:
                filled_results.append(self.execute_market_order(order, bar))
            elif order.order_type == OrderType.LIMIT:
                filled = False
                if order.side == OrderSide.BUY:
                    if bar.low <= order.limit_price:  # Limit buy trigger
                        fill_base = min(bar.open, order.limit_price)
                        slip_unit = self.calculate_slippage(fill_base, order.side)
                        fill_price = fill_base + slip_unit
                        traded_value = fill_price * order.quantity
                        commission = self.calculate_commission(traded_value)

                        order.status = OrderStatus.FILLED
                        order.filled_at = bar.timestamp
                        order.filled_price = fill_price
                        order.commission = commission
                        order.slippage = abs(slip_unit * order.quantity)

                        filled_results.append(
                            ExecutionResult(
                                order=order,
                                fill_price=fill_price,
                                commission=commission,
                                slippage=order.slippage,
                                timestamp=bar.timestamp,
                            )
                        )
                        filled = True
                elif order.side == OrderSide.SELL:
                    if bar.high >= order.limit_price:  # Limit sell trigger
                        fill_base = max(bar.open, order.limit_price)
                        slip_unit = self.calculate_slippage(fill_base, order.side)
                        fill_price = fill_base + slip_unit
                        traded_value = fill_price * order.quantity
                        commission = self.calculate_commission(traded_value)

                        order.status = OrderStatus.FILLED
                        order.filled_at = bar.timestamp
                        order.filled_price = fill_price
                        order.commission = commission
                        order.slippage = abs(slip_unit * order.quantity)

                        filled_results.append(
                            ExecutionResult(
                                order=order,
                                fill_price=fill_price,
                                commission=commission,
                                slippage=order.slippage,
                                timestamp=bar.timestamp,
                            )
                        )
                        filled = True

                if not filled:
                    unfilled_orders.append(order)

            elif order.order_type == OrderType.STOP_LOSS:
                filled = False
                if order.side == OrderSide.SELL:
                    if bar.low <= order.stop_price:  # Stop-loss sell trigger
                        fill_base = min(bar.open, order.stop_price)
                        slip_unit = self.calculate_slippage(fill_base, order.side)
                        fill_price = fill_base + slip_unit
                        traded_value = fill_price * order.quantity
                        commission = self.calculate_commission(traded_value)

                        order.status = OrderStatus.FILLED
                        order.filled_at = bar.timestamp
                        order.filled_price = fill_price
                        order.commission = commission
                        order.slippage = abs(slip_unit * order.quantity)

                        filled_results.append(
                            ExecutionResult(
                                order=order,
                                fill_price=fill_price,
                                commission=commission,
                                slippage=order.slippage,
                                timestamp=bar.timestamp,
                            )
                        )
                        filled = True
                elif order.side == OrderSide.BUY:
                    if bar.high >= order.stop_price:  # Stop-loss buy trigger
                        fill_base = max(bar.open, order.stop_price)
                        slip_unit = self.calculate_slippage(fill_base, order.side)
                        fill_price = fill_base + slip_unit
                        traded_value = fill_price * order.quantity
                        commission = self.calculate_commission(traded_value)

                        order.status = OrderStatus.FILLED
                        order.filled_at = bar.timestamp
                        order.filled_price = fill_price
                        order.commission = commission
                        order.slippage = abs(slip_unit * order.quantity)

                        filled_results.append(
                            ExecutionResult(
                                order=order,
                                fill_price=fill_price,
                                commission=commission,
                                slippage=order.slippage,
                                timestamp=bar.timestamp,
                            )
                        )
                        filled = True

                if not filled:
                    unfilled_orders.append(order)

        self.pending_orders = unfilled_orders
        return filled_results
