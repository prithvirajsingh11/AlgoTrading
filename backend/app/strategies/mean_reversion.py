"""Mean reversion strategy (reserved for subsequent phase)."""
from backend.app.strategies.base import BaseStrategy
from backend.app.data.loader import OHLCVBar
from backend.app.backtesting.orders import SignalEvent
from typing import Optional
import pandas as pd


class MeanReversionStrategy(BaseStrategy):
    """Mean reversion strategy stub.

    ponytail: To be implemented in subsequent strategy development phase.
    """

    def __init__(self, symbol: str, *args, **kwargs):
        super().__init__(name="MeanReversion", symbol=symbol)

    def generate_signal(self, bar: OHLCVBar, history_df: pd.DataFrame) -> Optional[SignalEvent]:
        raise NotImplementedError("MeanReversionStrategy will be implemented in subsequent phase.")
