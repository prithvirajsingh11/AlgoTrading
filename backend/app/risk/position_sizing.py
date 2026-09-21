from abc import ABC, abstractmethod
import math
from backend.app.backtesting.portfolio import Portfolio


class BasePositionSizer(ABC):
    """Abstract interface for algorithmic position sizing."""

    @abstractmethod
    def calculate_quantity(self, symbol: str, price: float, portfolio: Portfolio) -> float:
        """Determines share quantity to trade based on current price and portfolio equity."""
        pass


class FixedQuantitySizer(BasePositionSizer):
    """Orders a fixed number of shares per trade signal."""

    def __init__(self, quantity: float = 100.0):
        if quantity <= 0:
            raise ValueError("Quantity must be positive.")
        self.quantity = quantity

    def calculate_quantity(self, symbol: str, price: float, portfolio: Portfolio) -> float:
        return self.quantity


class PercentEquitySizer(BasePositionSizer):
    """Allocates a fixed percentage of total portfolio equity per position."""

    def __init__(self, percent_equity: float = 0.10, allow_fractional: bool = False):
        if not (0.0 < percent_equity <= 1.0):
            raise ValueError("percent_equity must be between 0 and 1.0")
        self.percent_equity = percent_equity
        self.allow_fractional = allow_fractional

    def calculate_quantity(self, symbol: str, price: float, portfolio: Portfolio) -> float:
        if price <= 0:
            return 0.0
        total_equity = portfolio.get_total_equity({symbol: price})
        target_allocation = total_equity * self.percent_equity
        raw_qty = target_allocation / price

        if not self.allow_fractional:
            return float(math.floor(raw_qty))
        return raw_qty
