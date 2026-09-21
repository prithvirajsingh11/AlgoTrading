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

    def cancel_orders_for_symbol(self, symbol: str, order_type: Optional[OrderType] = None) -> int:
        """Cancels pending orders for a given symbol, optionally filtered by order type."""
        cancelled = 0
        remaining = []
        for order in self.pending_orders:
            if order.symbol == symbol and (order_type is None or order.order_type == order_type):
                order.status = OrderStatus.CANCELLED
                cancelled += 1
            else:
                remaining.append(order)
        self.pending_orders = remaining
        return cancelled

    def get_pending_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Returns list of currently pending orders, optionally filtered by symbol."""
        if symbol is None:
            return list(self.pending_orders)
        return [o for o in self.pending_orders if o.symbol == symbol]

    def process_pending_orders(self, bar: OHLCVBar) -> List[ExecutionResult]:
        """Evaluates pending orders against current bar prices.
        
        Evaluates STOP_LOSS before LIMIT (pessimistic risk-first execution policy).
        Applies deterministic gap policy for stop-loss orders:
          - Long stop (SELL): gap-down fills at bar.open; intrabar fills at order.stop_price
          - Short stop (BUY): gap-up fills at bar.open; intrabar fills at order.stop_price
        """
        filled_results: List[ExecutionResult] = []
        unfilled_orders: List[Order] = []
        stopped_out_symbols: Dict[str, OrderSide] = {}

        # Pessimistic risk-first ordering: MARKET -> STOP_LOSS -> LIMIT
        def _order_priority(o: Order) -> int:
            if o.order_type == OrderType.MARKET:
                return 0
            if o.order_type == OrderType.STOP_LOSS:
                return 1
            return 2

        sorted_pending = sorted(self.pending_orders, key=_order_priority)

        for order in sorted_pending:
            if bar.symbol and order.symbol != bar.symbol:
                unfilled_orders.append(order)
                continue

            if order.order_type == OrderType.MARKET:
                filled_results.append(self.execute_market_order(order, bar))
            elif order.order_type == OrderType.STOP_LOSS:
                filled = False
                if order.side == OrderSide.SELL:
                    if bar.low <= order.stop_price:  # Stop-loss sell trigger
                        order.status = OrderStatus.TRIGGERED
                        if bar.open <= order.stop_price:  # Gap-down
                            fill_base = bar.open
                        else:  # Crossed intrabar or touched
                            fill_base = order.stop_price

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
                        stopped_out_symbols[order.symbol] = order.side
                elif order.side == OrderSide.BUY:
                    if bar.high >= order.stop_price:  # Stop-loss buy trigger
                        order.status = OrderStatus.TRIGGERED
                        if bar.open >= order.stop_price:  # Gap-up
                            fill_base = bar.open
                        else:  # Crossed intrabar or touched
                            fill_base = order.stop_price

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
                        stopped_out_symbols[order.symbol] = order.side

                if not filled:
                    unfilled_orders.append(order)

            elif order.order_type == OrderType.LIMIT:
                # If stopped out in this same bar on the same side/asset, cancel/suppress conflicting limit exit
                if order.symbol in stopped_out_symbols and order.side == stopped_out_symbols[order.symbol]:
                    order.status = OrderStatus.CANCELLED
                    continue

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

        self.pending_orders = unfilled_orders
        return filled_results
