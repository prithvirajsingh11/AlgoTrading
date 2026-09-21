"""ML-driven trading strategy (reserved for ML phase)."""
from backend.app.strategies.base import BaseStrategy
from backend.app.data.loader import OHLCVBar
from backend.app.backtesting.orders import SignalEvent
from typing import Optional
import pandas as pd


class MLTradingStrategy(BaseStrategy):
    """Machine learning model trading strategy stub.

    ponytail: To be implemented in subsequent ML integration phase.
    """

    def __init__(self, symbol: str, *args, **kwargs):
        super().__init__(name="MLTradingStrategy", symbol=symbol)

    def generate_signal(self, bar: OHLCVBar, history_df: pd.DataFrame) -> Optional[SignalEvent]:
        raise NotImplementedError("MLTradingStrategy will be implemented in subsequent ML phase.")
