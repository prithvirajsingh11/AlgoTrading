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
        if self.quantity > 0:
            return (current_price - self.avg_entry_price) * self.quantity
        else:
            return (self.avg_entry_price - current_price) * abs(self.quantity)


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
            "timestamp": self.timestamp.isoformat() if hasattr(self.timestamp, "isoformat") else str(self.timestamp),
            "cash": round(self.cash, 2),
            "positions_value": round(self.positions_value, 2),
            "total_equity": round(self.total_equity, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
        }


class Portfolio:
    """Manages cash balances, open positions, trade histories, and equity valuation."""

    def __init__(self, initial_cash: float = 100_000.0, allow_shorting: bool = False):
        if initial_cash <= 0:
            raise ValueError(f"Initial cash must be positive, got {initial_cash}")
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.allow_shorting = allow_shorting
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

            # If currently flat or long: add to long
            if pos.quantity >= 0:
                new_qty = pos.quantity + qty
                if pos.quantity > 0:
                    pos.avg_entry_price = ((pos.quantity * pos.avg_entry_price) + (qty * fill_price)) / new_qty
                else:
                    pos.avg_entry_price = fill_price
                    self._entry_times[symbol] = execution.timestamp
                pos.quantity = new_qty

            # If currently short: BUY covers the short position
            else:
                current_short_qty = abs(pos.quantity)
                cover_qty = min(current_short_qty, qty)
                excess_long_qty = qty - cover_qty

                # Realized P&L on covering short: (entry - fill) * cover_qty - fees
                pnl = (pos.avg_entry_price - fill_price) * cover_qty - commission - slippage
                pnl_pct = (pos.avg_entry_price - fill_price) / pos.avg_entry_price if pos.avg_entry_price > 0 else 0.0
                self.cumulative_realized_pnl += pnl

                entry_dt = self._entry_times.get(symbol, execution.timestamp)
                trade_record = TradeRecord(
                    symbol=symbol,
                    side=OrderSide.SELL,  # Original trade direction was short
                    quantity=cover_qty,
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

                pos.quantity += cover_qty
                if pos.quantity == 0:
                    pos.avg_entry_price = 0.0
                    self._entry_times.pop(symbol, None)

                # If order flipped short into long
                if excess_long_qty > 0:
                    pos.quantity = excess_long_qty
                    pos.avg_entry_price = fill_price
                    self._entry_times[symbol] = execution.timestamp

        elif order.side == OrderSide.SELL:
            gross_revenue = fill_price * qty
            net_revenue = gross_revenue - commission
            self.cash += net_revenue

            # If currently flat or short: open/add to short
            if pos.quantity <= 0:
                if not self.allow_shorting and pos.quantity == 0:
                    raise ValueError(
                        f"Attempted to sell {qty} shares of {symbol}, but only {pos.quantity} held."
                    )
                current_short = abs(pos.quantity)
                new_short = current_short + qty
                if current_short > 0:
                    pos.avg_entry_price = ((current_short * pos.avg_entry_price) + (qty * fill_price)) / new_short
                else:
                    pos.avg_entry_price = fill_price
                    self._entry_times[symbol] = execution.timestamp
                pos.quantity = -new_short

            # If currently long: SELL closes/reduces long
            else:
                if pos.quantity >= qty:
                    pnl = (fill_price - pos.avg_entry_price) * qty - commission - slippage
                    pnl_pct = (fill_price - pos.avg_entry_price) / pos.avg_entry_price if pos.avg_entry_price > 0 else 0.0
                    self.cumulative_realized_pnl += pnl

                    entry_dt = self._entry_times.get(symbol, execution.timestamp)
                    trade_record = TradeRecord(
                        symbol=symbol,
                        side=OrderSide.BUY,  # Original trade direction was long
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
                    if not self.allow_shorting:
                        raise ValueError(
                            f"Attempted to sell {qty} shares of {symbol}, but only {pos.quantity} held."
                        )
                    # Flips from long to short
                    held_long = pos.quantity
                    excess_short = qty - held_long

                    pnl = (fill_price - pos.avg_entry_price) * held_long - commission - slippage
                    pnl_pct = (fill_price - pos.avg_entry_price) / pos.avg_entry_price if pos.avg_entry_price > 0 else 0.0
                    self.cumulative_realized_pnl += pnl

                    entry_dt = self._entry_times.get(symbol, execution.timestamp)
                    trade_record = TradeRecord(
                        symbol=symbol,
                        side=OrderSide.BUY,
                        quantity=held_long,
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

                    pos.quantity = -excess_short
                    pos.avg_entry_price = fill_price
                    self._entry_times[symbol] = execution.timestamp

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
