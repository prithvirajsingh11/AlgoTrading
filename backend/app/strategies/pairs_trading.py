"""Pairs trading strategy (reserved for statistical arbitrage phase)."""
from backend.app.strategies.base import BaseStrategy
from backend.app.data.loader import OHLCVBar
from backend.app.backtesting.orders import SignalEvent
from typing import Optional
import pandas as pd


class PairsTradingStrategy(BaseStrategy):
    """Pairs trading statistical arbitrage strategy stub.

    ponytail: To be implemented in subsequent strategy development phase.
    """

    def __init__(self, symbol: str, hedge_symbol: str, *args, **kwargs):
        super().__init__(name="PairsTrading", symbol=symbol)
        self.hedge_symbol = hedge_symbol

    def generate_signal(self, bar: OHLCVBar, history_df: pd.DataFrame) -> Optional[SignalEvent]:
        raise NotImplementedError("PairsTradingStrategy will be implemented in subsequent phase.")
