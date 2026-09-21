"""Paper order lifecycle, execution records, and rejection tracking."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
import uuid

from backend.app.backtesting.orders import (
    Order,
    OrderType,
    OrderSide,
    OrderStatus,
    ExecutionResult,
)


@dataclass
class PaperOrderRecord:
    """Full persistent audit record for paper orders."""

    order_id: str
    session_id: str
    timestamp: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    requested_price: Optional[float] = None
    fill_price: Optional[float] = None
    status: str = "PENDING"
    commission: float = 0.0
    slippage: float = 0.0
    rejection_reason: Optional[str] = None
    strategy_name: str = ""
    provider: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": self.quantity,
            "requested_price": round(self.requested_price, 2) if self.requested_price else None,
            "fill_price": round(self.fill_price, 2) if self.fill_price else None,
            "status": self.status,
            "commission": round(self.commission, 4),
            "slippage": round(self.slippage, 4),
            "rejection_reason": self.rejection_reason,
            "strategy_name": self.strategy_name,
            "provider": self.provider,
        }


class PaperOrderManager:
    """Manages order submission, validation states, and execution histories for a paper session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.orders: Dict[str, PaperOrderRecord] = {}

    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        timestamp: datetime,
        requested_price: Optional[float] = None,
        strategy_name: str = "",
        provider: str = "",
    ) -> PaperOrderRecord:
        oid = f"ord_{uuid.uuid4().hex[:8]}"
        rec = PaperOrderRecord(
            order_id=oid,
            session_id=self.session_id,
            timestamp=timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp),
            symbol=symbol,
            side=side.value,
            order_type=order_type.value,
            quantity=quantity,
            requested_price=requested_price,
            status=OrderStatus.PENDING.value,
            strategy_name=strategy_name,
            provider=provider,
        )
        self.orders[oid] = rec
        return rec

    def record_rejection(self, order_id: str, reason: str) -> None:
        if order_id in self.orders:
            self.orders[order_id].status = OrderStatus.REJECTED.value
            self.orders[order_id].rejection_reason = reason

    def record_fill(self, execution: ExecutionResult) -> None:
        oid = execution.order.order_id
        if oid in self.orders:
            self.orders[oid].status = OrderStatus.FILLED.value
            self.orders[oid].fill_price = execution.fill_price
            self.orders[oid].commission = execution.commission
            self.orders[oid].slippage = execution.slippage

    def record_cancellation(self, order_id: str) -> None:
        if order_id in self.orders:
            self.orders[order_id].status = OrderStatus.CANCELLED.value

    def get_orders(self) -> List[PaperOrderRecord]:
        return list(self.orders.values())

    def get_pending_orders(self) -> List[PaperOrderRecord]:
        return [o for o in self.orders.values() if o.status == OrderStatus.PENDING.value]
