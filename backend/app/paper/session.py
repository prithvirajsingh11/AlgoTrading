"""Paper Trading Session domain model and lifecycle states."""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List, Optional
import uuid


class SessionStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class SessionMode(str, Enum):
    HISTORICAL_REPLAY = "HISTORICAL_REPLAY"
    SYNTHETIC_STREAM = "SYNTHETIC_STREAM"
    REAL_TIME = "REAL_TIME"


class SignalSafetyState(str, Enum):
    SIGNALS_ENABLED = "SIGNALS_ENABLED"
    SIGNALS_PAUSED = "SIGNALS_PAUSED"


class ReplaySpeed(str, Enum):
    HALF = "0.5x"
    ONE = "1x"
    TWO = "2x"
    FIVE = "5x"
    TEN = "10x"
    MAX = "MAX"

    @property
    def sleep_seconds(self) -> float:
        mapping = {
            "0.5x": 2.0,
            "1x": 1.0,
            "2x": 0.5,
            "5x": 0.2,
            "10x": 0.1,
            "MAX": 0.0,
        }
        return mapping.get(self.value, 1.0)


@dataclass
class PaperTradingSession:
    """Manages state and configuration for a persistent paper-trading session."""

    session_id: str = field(default_factory=lambda: f"paper_{uuid.uuid4().hex[:10]}")
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    stopped_at: Optional[str] = None

    dataset_id: str = "AAPL"
    symbols: List[str] = field(default_factory=lambda: ["AAPL"])
    timeframe: str = "1d"
    strategy: str = "TimeSeriesMomentum"
    strategy_params: Dict[str, Any] = field(default_factory=dict)
    provider: str = "rule_based"  # Decision layer: "rule_based", "xgboost", "typesafe_jev"

    # Real-time, streaming, and safety attributes
    mode: str = SessionMode.HISTORICAL_REPLAY.value
    data_provider_type: str = "HISTORICAL"  # "HISTORICAL", "SYNTHETIC", "LIVE_PROVIDER"
    safety_state: str = SignalSafetyState.SIGNALS_ENABLED.value
    max_data_age_seconds: float = 15.0
    last_data_timestamp: Optional[str] = None
    last_receive_timestamp: Optional[str] = None
    latency_ms: Optional[float] = None
    connection_state: str = "DISCONNECTED"
    reconnect_count: int = 0
    is_stale: bool = False
    bar_interval: str = "1m"
    decision_source: str = "RULE_BASED"

    initial_capital: float = 100_000.0
    current_equity: float = 100_000.0
    cash: float = 100_000.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    current_exposure: float = 0.0

    speed: str = ReplaySpeed.ONE.value
    status: SessionStatus = SessionStatus.CREATED
    error_message: Optional[str] = None

    current_bar_index: int = 0
    total_bars: int = 0
    simulation_timestamp: Optional[str] = None

    seed: int = 42
    jev_config: Optional[Dict[str, Any]] = None
    ml_config: Optional[Dict[str, Any]] = None
    execution_config: Dict[str, Any] = field(default_factory=lambda: {
        "commission_fixed": 1.0,
        "commission_percent": 0.0005,
        "slippage_bps": 5.0,
    })
    risk_config: Dict[str, Any] = field(default_factory=lambda: {
        "max_position_pct": 0.50,
        "max_drawdown_limit": 0.30,
        "allow_shorting": False,
        "position_size_pct": 0.20,
    })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "dataset_id": self.dataset_id,
            "symbols": self.symbols,
            "timeframe": self.timeframe,
            "strategy": self.strategy,
            "strategy_params": self.strategy_params,
            "provider": self.provider,
            "mode": self.mode,
            "data_provider_type": self.data_provider_type,
            "safety_state": self.safety_state,
            "max_data_age_seconds": self.max_data_age_seconds,
            "last_data_timestamp": self.last_data_timestamp,
            "last_receive_timestamp": self.last_receive_timestamp,
            "latency_ms": self.latency_ms,
            "connection_state": self.connection_state,
            "reconnect_count": self.reconnect_count,
            "is_stale": self.is_stale,
            "bar_interval": self.bar_interval,
            "decision_source": self.decision_source,
            "initial_capital": self.initial_capital,
            "current_equity": round(self.current_equity, 2),
            "cash": round(self.cash, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": round(self.unrealized_pnl, 2),
            "current_exposure": round(self.current_exposure, 4),
            "speed": self.speed,
            "status": self.status.value,
            "error_message": self.error_message,
            "current_bar_index": self.current_bar_index,
            "total_bars": self.total_bars,
            "simulation_timestamp": self.simulation_timestamp,
            "seed": self.seed,
            "jev_config": self.jev_config,
            "ml_config": self.ml_config,
            "execution_config": self.execution_config,
            "risk_config": self.risk_config,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PaperTradingSession:
        return cls(
            session_id=data.get("session_id", f"paper_{uuid.uuid4().hex[:10]}"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            started_at=data.get("started_at"),
            stopped_at=data.get("stopped_at"),
            dataset_id=data.get("dataset_id", "AAPL"),
            symbols=data.get("symbols", ["AAPL"]),
            timeframe=data.get("timeframe", "1d"),
            strategy=data.get("strategy", "TimeSeriesMomentum"),
            strategy_params=data.get("strategy_params", {}),
            provider=data.get("provider", "rule_based"),
            mode=data.get("mode", SessionMode.HISTORICAL_REPLAY.value),
            data_provider_type=data.get("data_provider_type", data.get("provider_type", "HISTORICAL")),
            safety_state=data.get("safety_state", SignalSafetyState.SIGNALS_ENABLED.value),
            max_data_age_seconds=float(data.get("max_data_age_seconds", 15.0)),
            last_data_timestamp=data.get("last_data_timestamp"),
            last_receive_timestamp=data.get("last_receive_timestamp"),
            latency_ms=data.get("latency_ms"),
            connection_state=data.get("connection_state", "DISCONNECTED"),
            reconnect_count=int(data.get("reconnect_count", 0)),
            is_stale=bool(data.get("is_stale", False)),
            bar_interval=data.get("bar_interval", "1m"),
            decision_source=data.get("decision_source", "RULE_BASED"),
            initial_capital=float(data.get("initial_capital", 100_000.0)),
            current_equity=float(data.get("current_equity", 100_000.0)),
            cash=float(data.get("cash", 100_000.0)),
            realized_pnl=float(data.get("realized_pnl", 0.0)),
            unrealized_pnl=float(data.get("unrealized_pnl", 0.0)),
            current_exposure=float(data.get("current_exposure", 0.0)),
            speed=data.get("speed", ReplaySpeed.ONE.value),
            status=SessionStatus(data.get("status", SessionStatus.CREATED.value)),
            error_message=data.get("error_message"),
            current_bar_index=int(data.get("current_bar_index", 0)),
            total_bars=int(data.get("total_bars", 0)),
            simulation_timestamp=data.get("simulation_timestamp"),
            seed=int(data.get("seed", 42)),
            jev_config=data.get("jev_config"),
            ml_config=data.get("ml_config"),
            execution_config=data.get("execution_config", {
                "commission_fixed": 1.0,
                "commission_percent": 0.0005,
                "slippage_bps": 5.0,
            }),
            risk_config=data.get("risk_config", {
                "max_position_pct": 0.50,
                "max_drawdown_limit": 0.30,
                "allow_shorting": False,
                "position_size_pct": 0.20,
            }),
        )

