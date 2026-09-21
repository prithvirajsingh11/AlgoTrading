from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import pandas as pd
from backend.app.data.loader import OHLCVBar
from backend.app.backtesting.orders import SignalEvent


class BaseStrategy(ABC):
    """Abstract Base Class for all trading strategies."""

    def __init__(self, name: str, symbol: str, parameters: Optional[Dict[str, Any]] = None):
        self.name = name
        self.symbol = symbol
        self.parameters = parameters or {}
        self.warmup_period: int = 1

    @abstractmethod
    def generate_signal(self, bar: OHLCVBar, history_df: pd.DataFrame) -> Optional[SignalEvent]:
        """Evaluates incoming market bar and historical slice to emit trading signals.

        history_df contains historical bars strictly UP TO AND INCLUDING the current bar.
        Must return None or SignalEvent (BUY, SELL, HOLD).
        """
        pass

    def reset(self) -> None:
        """Resets internal state between backtest runs."""
        pass
