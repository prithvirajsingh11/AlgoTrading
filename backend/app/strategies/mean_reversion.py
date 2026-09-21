from typing import Dict, Any, Optional
import pandas as pd
from backend.app.strategies.base import BaseStrategy
from backend.app.data.loader import OHLCVBar
from backend.app.backtesting.orders import SignalEvent, SignalType


class MeanReversionStrategy(BaseStrategy):
    """Statistical Mean Reversion Strategy.

    Calculates rolling mean and standard deviation over a configurable lookback window,
    computing the price z-score: z = (Close - mean) / std.
    Emits BUY signal when price is oversold (z <= entry_z_score).
    Emits SELL signal when price reverts to the mean (z >= exit_z_score).
    """

    def __init__(
        self,
        symbol: str,
        lookback_period: int = 20,
        entry_z_score: float = -2.0,
        exit_z_score: float = 0.0,
        stop_loss_pct: Optional[float] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        params = parameters or {}
        lookback = int(params.get("lookback_period", lookback_period))
        entry_z = float(params.get("entry_z_score", entry_z_score))
        exit_z = float(params.get("exit_z_score", exit_z_score))
        stop_loss = params.get("stop_loss_pct", stop_loss_pct)
        if stop_loss is not None:
            stop_loss = float(stop_loss)

        if lookback < 2:
            raise ValueError("lookback_period must be at least 2.")
        if entry_z >= exit_z:
            raise ValueError(f"entry_z_score ({entry_z}) must be strictly less than exit_z_score ({exit_z}).")
        if stop_loss is not None and not (0.0 < stop_loss < 1.0):
            raise ValueError("stop_loss_pct must be between 0 and 1.0.")

        super().__init__(
            name="MeanReversion",
            symbol=symbol,
            parameters={
                "lookback_period": lookback,
                "entry_z_score": entry_z,
                "exit_z_score": exit_z,
                "stop_loss_pct": stop_loss,
            },
        )
        self.lookback_period = lookback
        self.entry_z_score = entry_z
        self.exit_z_score = exit_z
        self.stop_loss_pct = stop_loss
        self.warmup_period = lookback
        self._is_long: bool = False

    def reset(self) -> None:
        self._is_long = False

    @staticmethod
    def calculate_z_score(price: float, mean: float, std: float) -> float:
        if std <= 1e-8:
            return 0.0
        return (price - mean) / std

    def generate_signal(self, bar: OHLCVBar, history_df: pd.DataFrame) -> Optional[SignalEvent]:
        if len(history_df) < self.warmup_period:
            return None

        # Slicing strictly up to and including the current bar
        window_closes = history_df["close"].iloc[-self.lookback_period:]
        mean_val = float(window_closes.mean())
        std_val = float(window_closes.std(ddof=1))

        if pd.isna(mean_val) or pd.isna(std_val) or std_val <= 1e-8:
            return None

        z_score = self.calculate_z_score(bar.close, mean_val, std_val)

        # Oversold entry
        if z_score <= self.entry_z_score:
            if not self._is_long:
                self._is_long = True
                stop_price = bar.close * (1.0 - self.stop_loss_pct) if self.stop_loss_pct else None
                return SignalEvent(
                    timestamp=bar.timestamp,
                    symbol=self.symbol,
                    signal_type=SignalType.BUY,
                    stop_loss_price=stop_price,
                    metadata={
                        "z_score": round(z_score, 4),
                        "mean": round(mean_val, 2),
                        "std": round(std_val, 4),
                        "entry_z_score": self.entry_z_score,
                        "stop_loss": stop_price,
                    },
                )

        # Reversion exit
        elif z_score >= self.exit_z_score:
            if self._is_long:
                self._is_long = False
                return SignalEvent(
                    timestamp=bar.timestamp,
                    symbol=self.symbol,
                    signal_type=SignalType.SELL,
                    metadata={
                        "z_score": round(z_score, 4),
                        "mean": round(mean_val, 2),
                        "std": round(std_val, 4),
                        "exit_z_score": self.exit_z_score,
                    },
                )

        return None
