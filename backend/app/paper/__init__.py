"""AlgoTrade Paper Trading module for realistic simulated execution with zero lookahead bias."""

from backend.app.paper.session import PaperTradingSession, SessionStatus, ReplaySpeed
from backend.app.paper.events import (
    PaperEvent,
    MarketEvent,
    StrategySignalEvent,
    RiskValidationEvent,
    OrderLifecycleEvent,
    FillExecutionEvent,
    PortfolioUpdateEvent,
    SessionLifecycleEvent,
)
from backend.app.paper.market_data import MarketDataProvider, HistoricalReplayProvider
from backend.app.paper.account import PaperAccount
from backend.app.paper.orders import PaperOrderRecord, PaperOrderManager
from backend.app.paper.storage import SQLitePaperStorage
from backend.app.paper.service import PaperTradingService, paper_service

__all__ = [
    "PaperTradingSession",
    "SessionStatus",
    "ReplaySpeed",
    "PaperEvent",
    "MarketEvent",
    "StrategySignalEvent",
    "RiskValidationEvent",
    "OrderLifecycleEvent",
    "FillExecutionEvent",
    "PortfolioUpdateEvent",
    "SessionLifecycleEvent",
    "MarketDataProvider",
    "HistoricalReplayProvider",
    "PaperAccount",
    "PaperOrderRecord",
    "PaperOrderManager",
    "SQLitePaperStorage",
    "PaperTradingService",
    "paper_service",
]
