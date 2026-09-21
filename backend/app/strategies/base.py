from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Union, List
import pandas as pd
from backend.app.data.loader import OHLCVBar, MarketSnapshot
from backend.app.backtesting.orders import SignalEvent


class BaseStrategy(ABC):
    """Abstract Base Class for all trading strategies."""

    def __init__(self, name: str, symbol: str, parameters: Optional[Dict[str, Any]] = None):
        self.name = name
        self.symbol = symbol
        self.parameters = parameters or {}
        self.warmup_period: int = 1

    @abstractmethod
    def generate_signal(
        self,
        bar: Union[OHLCVBar, MarketSnapshot],
        history_df: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
    ) -> Optional[Union[SignalEvent, List[SignalEvent]]]:
        """Evaluates incoming market bar and historical slice to emit trading signals.

        history_df contains historical bars strictly UP TO AND INCLUDING the current bar.
        Must return None, SignalEvent, or List[SignalEvent].
        """
        pass

    def reset(self) -> None:
        """Resets internal state between backtest runs."""
        pass
