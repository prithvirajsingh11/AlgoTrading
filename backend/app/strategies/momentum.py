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


class TimeSeriesMomentumStrategy(BaseStrategy):
    """Time-series return momentum strategy.

    Buys when the N-period historical return exceeds an entry threshold.
    Exits/sells when the return drops below an exit threshold or reaches stop-loss.
    """

    def __init__(
        self,
        symbol: str,
        lookback_period: int = 20,
        entry_threshold: float = 0.02,
        exit_threshold: float = -0.01,
        stop_loss_pct: Optional[float] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        params = parameters or {}
        lookback = int(params.get("lookback_period", lookback_period))
        entry_thresh = float(params.get("entry_threshold", entry_threshold))
        exit_thresh = float(params.get("exit_threshold", exit_threshold))
        stop_loss = params.get("stop_loss_pct", stop_loss_pct)
        if stop_loss is not None:
            stop_loss = float(stop_loss)

        if lookback <= 0:
            raise ValueError("lookback_period must be a positive integer.")
        if entry_thresh <= exit_thresh:
            raise ValueError(f"entry_threshold ({entry_thresh}) must be greater than exit_threshold ({exit_thresh}).")
        if stop_loss is not None and not (0.0 < stop_loss < 1.0):
            raise ValueError("stop_loss_pct must be between 0 and 1.0.")

        super().__init__(
            name="TimeSeriesMomentum",
            symbol=symbol,
            parameters={
                "lookback_period": lookback,
                "entry_threshold": entry_thresh,
                "exit_threshold": exit_thresh,
                "stop_loss_pct": stop_loss,
            },
        )
        self.lookback_period = lookback
        self.entry_threshold = entry_thresh
        self.exit_threshold = exit_thresh
        self.stop_loss_pct = stop_loss
        self.warmup_period = lookback + 1
        self._is_long: bool = False

    def reset(self) -> None:
        self._is_long = False

    def generate_signal(self, bar: OHLCVBar, history_df: pd.DataFrame) -> Optional[SignalEvent]:
        if len(history_df) < self.warmup_period:
            return None

        closes = history_df["close"]
        past_close = closes.iloc[-1 - self.lookback_period]
        curr_close = bar.close

        if pd.isna(past_close) or past_close <= 0:
            return None

        momentum_return = (curr_close - past_close) / past_close

        # Entry signal
        if momentum_return >= self.entry_threshold:
            if not self._is_long:
                self._is_long = True
                stop_price = curr_close * (1.0 - self.stop_loss_pct) if self.stop_loss_pct else None
                return SignalEvent(
                    timestamp=bar.timestamp,
                    symbol=self.symbol,
                    signal_type=SignalType.BUY,
                    stop_loss_price=stop_price,
                    metadata={
                        "momentum_return": round(momentum_return, 4),
                        "entry_threshold": self.entry_threshold,
                        "past_close": past_close,
                        "stop_loss": stop_price,
                    },
                )

        # Exit signal
        elif momentum_return <= self.exit_threshold:
            if self._is_long:
                self._is_long = False
                return SignalEvent(
                    timestamp=bar.timestamp,
                    symbol=self.symbol,
                    signal_type=SignalType.SELL,
                    metadata={
                        "momentum_return": round(momentum_return, 4),
                        "exit_threshold": self.exit_threshold,
                        "past_close": past_close,
                    },
                )

        return None
