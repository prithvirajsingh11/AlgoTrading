"""Trading strategies package."""
from backend.app.strategies.base import BaseStrategy
from backend.app.strategies.momentum import MovingAverageCrossStrategy

__all__ = ["BaseStrategy", "MovingAverageCrossStrategy"]
