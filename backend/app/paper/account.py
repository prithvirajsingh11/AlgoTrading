"""Paper Account state management wrapping the authoritative Portfolio class."""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from datetime import datetime

from backend.app.backtesting.portfolio import Portfolio, Position, EquityPoint
from backend.app.backtesting.orders import ExecutionResult, TradeRecord


class PaperAccount:
    """Manages paper trading balance, portfolio accounting, and position states.
    
    Reuses the authoritative Portfolio class to ensure consistent P&L and risk metrics.
    """

    def __init__(self, initial_capital: float = 100_000.0, allow_shorting: bool = False):
        self.portfolio = Portfolio(initial_cash=initial_capital, allow_shorting=allow_shorting)
        self.initial_capital = initial_capital

    def update_fill(self, execution: ExecutionResult) -> Optional[TradeRecord]:
        """Applies broker fill to portfolio cash and positions."""
        return self.portfolio.update_fill(execution)

    def record_bar_equity(self, current_prices: Dict[str, float], timestamp: datetime) -> EquityPoint:
        """Records bar-end equity snapshot and updates portfolio valuation."""
        return self.portfolio.mark_to_market(timestamp, current_prices)

    def get_total_equity(self, current_prices: Optional[Dict[str, float]] = None) -> float:
        prices = current_prices or {}
        return self.portfolio.get_total_equity(prices)

    def get_cash(self) -> float:
        return self.portfolio.cash

    def get_realized_pnl(self) -> float:
        return self.portfolio.cumulative_realized_pnl

    def get_unrealized_pnl(self, current_prices: Dict[str, float]) -> float:
        total_unrealized = 0.0
        for sym, pos in self.portfolio.positions.items():
            if pos.quantity != 0 and sym in current_prices:
                total_unrealized += pos.unrealized_pnl(current_prices[sym])
        return total_unrealized

    def get_exposure(self, current_prices: Dict[str, float]) -> float:
        eq = self.get_total_equity(current_prices)
        if eq <= 0:
            return 0.0
        total_market_val = sum(
            abs(pos.quantity) * current_prices.get(sym, 0.0)
            for sym, pos in self.portfolio.positions.items()
            if pos.quantity != 0
        )
        return total_market_val / eq

    def get_positions_summary(self, current_prices: Dict[str, float]) -> List[Dict[str, Any]]:
        """Returns structured position summaries for API and UI rendering."""
        summary = []
        for sym, pos in self.portfolio.positions.items():
            if pos.quantity != 0:
                p = current_prices.get(sym, pos.avg_entry_price)
                mkt_val = pos.quantity * p
                unrealized = pos.unrealized_pnl(p)
                unrealized_pct = (unrealized / (abs(pos.quantity) * pos.avg_entry_price)) if pos.avg_entry_price > 0 else 0.0
                summary.append({
                    "symbol": sym,
                    "quantity": pos.quantity,
                    "avg_entry_price": round(pos.avg_entry_price, 2),
                    "current_price": round(p, 2),
                    "market_value": round(mkt_val, 2),
                    "unrealized_pnl": round(unrealized, 2),
                    "unrealized_pnl_pct": round(unrealized_pct, 4),
                    "direction": "LONG" if pos.quantity > 0 else "SHORT",
                })
        return summary

    def get_completed_trades(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self.portfolio.trades]

    def to_dict(self, current_prices: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        prices = current_prices or {}
        eq = self.get_total_equity(prices)
        return {
            "initial_capital": self.initial_capital,
            "cash": round(self.portfolio.cash, 2),
            "total_equity": round(eq, 2),
            "realized_pnl": round(self.portfolio.cumulative_realized_pnl, 2),
            "unrealized_pnl": round(self.get_unrealized_pnl(prices), 2),
            "current_exposure": round(self.get_exposure(prices), 4),
            "positions_count": len([p for p in self.portfolio.positions.values() if p.quantity != 0]),
            "trades_count": len(self.portfolio.trades),
        }
