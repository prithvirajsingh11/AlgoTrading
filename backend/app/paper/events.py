"""Structured internal events for paper trading with explicit simulation timestamps."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional


@dataclass(frozen=True)
class PaperEvent:
    """Base event containing explicit simulation timestamp."""

    timestamp: str
    event_type: str
    session_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "session_id": self.session_id,
        }


@dataclass(frozen=True)
class MarketEvent(PaperEvent):
    symbol: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    bar_index: int = 0
    total_bars: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "symbol": self.symbol,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "bar_index": self.bar_index,
            "total_bars": self.total_bars,
        })
        return d


@dataclass(frozen=True)
class StrategySignalEvent(PaperEvent):
    symbol: str = ""
    signal_type: str = "HOLD"  # BUY, SELL, HOLD
    strength: float = 1.0
    strategy_name: str = ""
    provider: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "symbol": self.symbol,
            "signal_type": self.signal_type,
            "strength": self.strength,
            "strategy_name": self.strategy_name,
            "provider": self.provider,
            "metadata": self.metadata,
        })
        return d


@dataclass(frozen=True)
class RiskValidationEvent(PaperEvent):
    symbol: str = ""
    approved: bool = True
    reason: Optional[str] = None
    requested_qty: float = 0.0
    approved_qty: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "symbol": self.symbol,
            "approved": self.approved,
            "reason": self.reason,
            "requested_qty": self.requested_qty,
            "approved_qty": self.approved_qty,
        })
        return d


@dataclass(frozen=True)
class OrderLifecycleEvent(PaperEvent):
    order_id: str = ""
    symbol: str = ""
    side: str = "BUY"
    order_type: str = "MARKET"
    quantity: float = 0.0
    price: Optional[float] = None
    status: str = "PENDING"
    rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": self.quantity,
            "price": self.price,
            "status": self.status,
            "rejection_reason": self.rejection_reason,
        })
        return d


@dataclass(frozen=True)
class FillExecutionEvent(PaperEvent):
    order_id: str = ""
    symbol: str = ""
    side: str = "BUY"
    quantity: float = 0.0
    fill_price: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "fill_price": self.fill_price,
            "commission": self.commission,
            "slippage": self.slippage,
        })
        return d


@dataclass(frozen=True)
class PortfolioUpdateEvent(PaperEvent):
    total_equity: float = 100_000.0
    cash: float = 100_000.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    current_exposure: float = 0.0
    positions: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "total_equity": round(self.total_equity, 2),
            "cash": round(self.cash, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "current_exposure": round(self.current_exposure, 4),
            "positions": self.positions,
        })
        return d


@dataclass(frozen=True)
class SessionLifecycleEvent(PaperEvent):
    status: str = "CREATED"
    current_bar: int = 0
    total_bars: int = 0
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "status": self.status,
            "current_bar": self.current_bar,
            "total_bars": self.total_bars,
            "message": self.message,
        })
        return d
