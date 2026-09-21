from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
import uuid


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    TRIGGERED = "TRIGGERED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class SignalEvent:
    timestamp: datetime
    symbol: str
    signal_type: SignalType
    strength: float = 1.0
    stop_loss_price: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Order:
    symbol: str
    order_type: OrderType
    side: OrderSide
    quantity: float
    created_at: datetime
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    order_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: OrderStatus = OrderStatus.PENDING
    filled_at: Optional[datetime] = None
    filled_price: Optional[float] = None
    commission: float = 0.0
    slippage: float = 0.0

    def __post_init__(self):
        if self.quantity <= 0:
            raise ValueError(f"Order quantity must be positive, got {self.quantity}")
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("Limit order requires limit_price")
        if self.order_type == OrderType.STOP_LOSS and self.stop_price is None:
            raise ValueError("Stop loss order requires stop_price")


@dataclass(frozen=True)
class ExecutionResult:
    order: Order
    fill_price: float
    commission: float
    slippage: float
    timestamp: datetime


@dataclass
class TradeRecord:
    symbol: str
    side: OrderSide
    quantity: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    commission: float
    slippage: float
    pnl: float
    pnl_percent: float
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "entry_time": self.entry_time.isoformat() if hasattr(self.entry_time, "isoformat") else str(self.entry_time),
            "exit_time": self.exit_time.isoformat() if hasattr(self.exit_time, "isoformat") else str(self.exit_time),
            "commission": self.commission,
            "slippage": self.slippage,
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
        }
