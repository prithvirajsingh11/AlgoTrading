"""Trading strategies package."""
from backend.app.strategies.base import BaseStrategy
from backend.app.strategies.momentum import (
    MovingAverageCrossStrategy,
    TimeSeriesMomentumStrategy,
)
from backend.app.strategies.mean_reversion import MeanReversionStrategy
from backend.app.strategies.pairs_trading import PairsTradingStrategy

__all__ = [
    "BaseStrategy",
    "MovingAverageCrossStrategy",
    "TimeSeriesMomentumStrategy",
    "MeanReversionStrategy",
    "PairsTradingStrategy",
]
