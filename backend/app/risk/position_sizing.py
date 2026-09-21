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


class RiskBasedPositionSizer(BasePositionSizer):
    """Calculates position size based on account equity, stop-loss distance, and risk percentage."""

    def __init__(
        self,
        risk_percent: float = 0.01,
        default_stop_loss_pct: float = 0.05,
        allow_fractional: bool = False,
    ):
        if not (0.0 < risk_percent <= 1.0):
            raise ValueError("risk_percent must be between 0 and 1.0")
        if not (0.0 < default_stop_loss_pct < 1.0):
            raise ValueError("default_stop_loss_pct must be between 0 and 1.0")
        self.risk_percent = risk_percent
        self.default_stop_loss_pct = default_stop_loss_pct
        self.allow_fractional = allow_fractional

    @staticmethod
    def calculate_risk_size(
        equity: float,
        entry_price: float,
        stop_loss_price: float,
        risk_percent: float,
        allow_fractional: bool = False,
    ) -> float:
        """Core risk sizing formula:
        risk_capital = equity * risk_percent
        risk_per_share = |entry_price - stop_loss_price|
        size = risk_capital / risk_per_share
        """
        if equity <= 0 or entry_price <= 0 or risk_percent <= 0:
            return 0.0
        risk_per_share = abs(entry_price - stop_loss_price)
        if risk_per_share <= 1e-8:
            return 0.0
        risk_capital = equity * risk_percent
        raw_qty = risk_capital / risk_per_share
        return raw_qty if allow_fractional else float(math.floor(raw_qty))

    def calculate_quantity(
        self,
        symbol: str,
        price: float,
        portfolio: Portfolio,
        stop_loss_price: Optional[float] = None,
    ) -> float:
        if price <= 0:
            return 0.0
        equity = portfolio.get_total_equity({symbol: price})
        if stop_loss_price is None:
            stop_loss_price = price * (1.0 - self.default_stop_loss_pct)
        return self.calculate_risk_size(
            equity=equity,
            entry_price=price,
            stop_loss_price=stop_loss_price,
            risk_percent=self.risk_percent,
            allow_fractional=self.allow_fractional,
        )
