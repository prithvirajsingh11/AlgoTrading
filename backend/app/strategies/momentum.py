from typing import Dict, Any, Optional
import pandas as pd
from backend.app.strategies.base import BaseStrategy
from backend.app.data.loader import OHLCVBar
from backend.app.backtesting.orders import SignalEvent, SignalType


class MovingAverageCrossStrategy(BaseStrategy):
    """Dual Moving Average Momentum / Trend Following Strategy.

    Buys when fast moving average crosses above slow moving average (Golden Cross).
    Sells when fast moving average crosses below slow moving average (Death Cross).
    """

    def __init__(
        self,
        symbol: str,
        fast_period: int = 10,
        slow_period: int = 30,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        params = parameters or {}
        fast = int(params.get("fast_period", fast_period))
        slow = int(params.get("slow_period", slow_period))

        if fast <= 0 or slow <= 0:
            raise ValueError("Moving average periods must be positive integers.")
        if fast >= slow:
            raise ValueError(f"fast_period ({fast}) must be strictly less than slow_period ({slow}).")

        super().__init__(
            name="MovingAverageCross",
            symbol=symbol,
            parameters={"fast_period": fast, "slow_period": slow},
        )
        self.fast_period = fast
        self.slow_period = slow
        self.warmup_period = slow + 1
        self._position_state: Optional[SignalType] = None

    def reset(self) -> None:
        self._position_state = None

    def generate_signal(self, bar: OHLCVBar, history_df: pd.DataFrame) -> Optional[SignalEvent]:
        # Enforce warmup window
        if len(history_df) < self.warmup_period:
            return None

        # Slicing the required tail to compute the two MAs
        closes = history_df["close"]
        fast_ma = closes.rolling(window=self.fast_period).mean()
        slow_ma = closes.rolling(window=self.slow_period).mean()

        curr_fast = fast_ma.iloc[-1]
        curr_slow = slow_ma.iloc[-1]
        prev_fast = fast_ma.iloc[-2]
        prev_slow = slow_ma.iloc[-2]

        # Check for NaN in calculated averages
        if pd.isna(curr_fast) or pd.isna(curr_slow) or pd.isna(prev_fast) or pd.isna(prev_slow):
            return None

        # Golden Cross: Fast MA crosses above Slow MA
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            if self._position_state != SignalType.BUY:
                self._position_state = SignalType.BUY
                return SignalEvent(
                    timestamp=bar.timestamp,
                    symbol=self.symbol,
                    signal_type=SignalType.BUY,
                    metadata={
                        "fast_ma": curr_fast,
                        "slow_ma": curr_slow,
                        "crossover": "golden_cross",
                    },
                )

        # Death Cross: Fast MA crosses below Slow MA
        elif prev_fast >= prev_slow and curr_fast < curr_slow:
            if self._position_state == SignalType.BUY:
                self._position_state = SignalType.SELL
                return SignalEvent(
                    timestamp=bar.timestamp,
                    symbol=self.symbol,
                    signal_type=SignalType.SELL,
                    metadata={
                        "fast_ma": curr_fast,
                        "slow_ma": curr_slow,
                        "crossover": "death_cross",
                    },
                )

        return None
