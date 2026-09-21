from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from backend.app.backtesting.orders import (
    OrderSide,
    ExecutionResult,
    TradeRecord,
)


@dataclass
class Position:
    symbol: str
    quantity: float = 0.0
    avg_entry_price: float = 0.0

    def market_value(self, current_price: float) -> float:
        return self.quantity * current_price

    def unrealized_pnl(self, current_price: float) -> float:
        if self.quantity == 0:
            return 0.0
        return (current_price - self.avg_entry_price) * self.quantity


@dataclass(frozen=True)
class EquityPoint:
    timestamp: datetime
    cash: float
    positions_value: float
    total_equity: float
    realized_pnl: float
    unrealized_pnl: float

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "cash": round(self.cash, 2),
            "positions_value": round(self.positions_value, 2),
            "total_equity": round(self.total_equity, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
        }


class Portfolio:
    """Manages cash balances, open positions, trade histories, and equity valuation."""

    def __init__(self, initial_cash: float = 100_000.0):
        if initial_cash <= 0:
            raise ValueError(f"Initial cash must be positive, got {initial_cash}")
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: Dict[str, Position] = {}
        self.trades: List[TradeRecord] = []
        self.equity_history: List[EquityPoint] = []
        self.cumulative_realized_pnl: float = 0.0
        self._entry_times: Dict[str, datetime] = {}

    def get_position(self, symbol: str) -> Position:
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol)
        return self.positions[symbol]

    def update_fill(self, execution: ExecutionResult) -> Optional[TradeRecord]:
        order = execution.order
        symbol = order.symbol
        qty = order.quantity
        fill_price = execution.fill_price
        commission = execution.commission
        slippage = execution.slippage
        pos = self.get_position(symbol)

        trade_record: Optional[TradeRecord] = None

        if order.side == OrderSide.BUY:
            total_cost = (fill_price * qty) + commission
            self.cash -= total_cost

            # Updating long position
            new_qty = pos.quantity + qty
            if pos.quantity > 0:
                pos.avg_entry_price = ((pos.quantity * pos.avg_entry_price) + (qty * fill_price)) / new_qty
            else:
                pos.avg_entry_price = fill_price
                self._entry_times[symbol] = execution.timestamp
            pos.quantity = new_qty

        elif order.side == OrderSide.SELL:
            gross_revenue = fill_price * qty
            net_revenue = gross_revenue - commission
            self.cash += net_revenue

            # Reducing/closing long position
            if pos.quantity >= qty:
                pnl = (fill_price - pos.avg_entry_price) * qty - commission - slippage
                pnl_pct = (fill_price - pos.avg_entry_price) / pos.avg_entry_price if pos.avg_entry_price > 0 else 0.0
                self.cumulative_realized_pnl += pnl

                entry_dt = self._entry_times.get(symbol, execution.timestamp)
                trade_record = TradeRecord(
                    symbol=symbol,
                    side=OrderSide.BUY,  # Underlying trade direction was long
                    quantity=qty,
                    entry_price=pos.avg_entry_price,
                    exit_price=fill_price,
                    entry_time=entry_dt,
                    exit_time=execution.timestamp,
                    commission=commission,
                    slippage=slippage,
                    pnl=pnl,
                    pnl_percent=pnl_pct,
                )
                self.trades.append(trade_record)

                pos.quantity -= qty
                if pos.quantity == 0:
                    pos.avg_entry_price = 0.0
                    self._entry_times.pop(symbol, None)
            else:
                raise ValueError(
                    f"Attempted to sell {qty} shares of {symbol}, but only {pos.quantity} held."
                )

        return trade_record

    def get_positions_value(self, current_prices: Dict[str, float]) -> float:
        total = 0.0
        for symbol, pos in self.positions.items():
            if pos.quantity != 0 and symbol in current_prices:
                total += pos.market_value(current_prices[symbol])
        return total

    def get_unrealized_pnl(self, current_prices: Dict[str, float]) -> float:
        total = 0.0
        for symbol, pos in self.positions.items():
            if pos.quantity != 0 and symbol in current_prices:
                total += pos.unrealized_pnl(current_prices[symbol])
        return total

    def get_total_equity(self, current_prices: Dict[str, float]) -> float:
        return self.cash + self.get_positions_value(current_prices)

    def mark_to_market(self, timestamp: datetime, current_prices: Dict[str, float]) -> EquityPoint:
        pos_val = self.get_positions_value(current_prices)
        unrealized = self.get_unrealized_pnl(current_prices)
        total_equity = self.cash + pos_val

        point = EquityPoint(
            timestamp=timestamp,
            cash=self.cash,
            positions_value=pos_val,
            total_equity=total_equity,
            realized_pnl=self.cumulative_realized_pnl,
            unrealized_pnl=unrealized,
        )
        self.equity_history.append(point)
        return point
