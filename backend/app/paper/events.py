"""Structured internal events for paper trading with explicit simulation timestamps."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional


@dataclass(frozen=True)
class PaperEvent:
    """Base event containing explicit simulation/live timestamp and optional receive timestamp."""

    timestamp: str
    event_type: str
    session_id: str
    received_at: Optional[str] = None
    correlation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        res = {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "session_id": self.session_id,
        }
        if self.received_at:
            res["received_at"] = self.received_at
        if self.correlation_id:
            res["correlation_id"] = self.correlation_id
        return res



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
    decision_source: str = "RULE_BASED"  # RULE_BASED, XGBOOST, JEV, JEV_ASSISTED
    model_version: Optional[str] = None
    jev_decision_mode: Optional[str] = None  # LIVE_JEV, CACHED_JEV
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "symbol": self.symbol,
            "signal_type": self.signal_type,
            "strength": self.strength,
            "strategy_name": self.strategy_name,
            "provider": self.provider,
            "decision_source": self.decision_source,
            "model_version": self.model_version,
            "jev_decision_mode": self.jev_decision_mode,
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


@dataclass(frozen=True)
class ProviderStatusEvent(PaperEvent):
    provider: str = ""
    status: str = "CONNECTED"
    connected: bool = True
    reconnect_count: int = 0
    latency_ms: Optional[float] = None
    is_stale: bool = False
    safety_state: str = "SIGNALS_ENABLED"
    last_heartbeat: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "provider": self.provider,
            "status": self.status,
            "connected": self.connected,
            "reconnect_count": self.reconnect_count,
            "latency_ms": self.latency_ms,
            "is_stale": self.is_stale,
            "safety_state": self.safety_state,
            "last_heartbeat": self.last_heartbeat,
            "error_message": self.error_message,
        })
        return d


@dataclass(frozen=True)
class MarketUpdateEvent(PaperEvent):
    symbol: str = ""
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: float = 0.0
    volume: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    mid: Optional[float] = None
    last_price: Optional[float] = None
    latency_ms: Optional[float] = None
    is_stale: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "symbol": self.symbol,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "bid": self.bid,
            "ask": self.ask,
            "mid": self.mid,
            "last_price": self.last_price,
            "latency_ms": self.latency_ms,
            "is_stale": self.is_stale,
        })
        return d


@dataclass(frozen=True)
class BarClosedEvent(PaperEvent):
    symbol: str = ""
    interval: str = "1m"
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: float = 0.0
    volume: float = 0.0
    bar_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "symbol": self.symbol,
            "interval": self.interval,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "bar_index": self.bar_index,
        })
        return d


@dataclass(frozen=True)
class ReconnectEvent(PaperEvent):
    provider: str = ""
    reconnect_attempt: int = 0
    max_attempts: int = 5
    backoff_seconds: float = 1.0
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "provider": self.provider,
            "reconnect_attempt": self.reconnect_attempt,
            "max_attempts": self.max_attempts,
            "backoff_seconds": self.backoff_seconds,
            "reason": self.reason,
        })
        return d


@dataclass(frozen=True)
class PaperErrorEvent(PaperEvent):
    error_type: str = "RUNTIME"
    message: str = ""
    detail: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "error_type": self.error_type,
            "message": self.message,
            "detail": self.detail,
        })
        return d


@dataclass(frozen=True)
class JevDecisionEvent(PaperEvent):
    symbol: str = ""
    decision: str = "NO_ACTION"
    confidence: float = 0.0
    mode: str = "LIVE_JEV"  # LIVE_JEV or CACHED_JEV
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "symbol": self.symbol,
            "decision": self.decision,
            "confidence": self.confidence,
            "mode": self.mode,
            "rationale": self.rationale,
        })
        return d


@dataclass(frozen=True)
class MLPredictionEvent(PaperEvent):
    symbol: str = ""
    model_version: str = "v1"
    prediction: float = 0.5
    features_used: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        d.update({
            "symbol": self.symbol,
            "model_version": self.model_version,
            "prediction": self.prediction,
            "features_used": self.features_used,
        })
        return d


