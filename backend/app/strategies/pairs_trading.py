"""Statistical Arbitrage Pairs Trading Strategy.

Statistical Assumptions & Methodology:
1. Cointegration: Asset 1 (symbol) and Asset 2 (hedge_symbol) are assumed to share an underlying
   economic link such that their price relationship forms a stationary, mean-reverting spread:
       Spread_t = Price_1,t - (beta * Price_2,t)
2. Hedge Ratio (beta): Estimated dynamically via rolling Ordinary Least Squares (OLS) regression:
       beta = Cov(Price_1, Price_2) / Var(Price_2)
   Alternatively, a fixed user-defined hedge ratio may be specified.
3. Stationarity & Gaussian Spread Deviation:
   The spread is normalized via rolling z-score:
       z_t = (Spread_t - mean(Spread)) / std(Spread)
   Under the mean-reversion hypothesis, extreme z-scores indicate temporary divergence:
   - When z_t <= -entry_threshold: Asset 1 is undervalued relative to Asset 2 -> BUY Asset 1.
   - When z_t >= -exit_threshold: Spread has reverted to equilibrium -> SELL / EXIT Asset 1.
4. No Lookahead Bias: All rolling statistics (beta, mean, std) are computed strictly using historical
   observations up to and including the current bar timestamp.
"""

from typing import Dict, Any, Optional
import numpy as np
import pandas as pd
from backend.app.strategies.base import BaseStrategy
from backend.app.data.loader import OHLCVBar
from backend.app.backtesting.orders import SignalEvent, SignalType


class PairsTradingStrategy(BaseStrategy):
    """Statistical Arbitrage Pairs Trading Strategy."""

    def __init__(
        self,
        symbol: str,
        hedge_symbol: str = "HEDGE",
        lookback_period: int = 30,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.5,
        fixed_hedge_ratio: Optional[float] = None,
        hedge_data: Optional[pd.DataFrame] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        params = parameters or {}
        lookback = int(params.get("lookback_period", lookback_period))
        entry_th = float(params.get("entry_threshold", entry_threshold))
        exit_th = float(params.get("exit_threshold", exit_threshold))
        h_sym = params.get("hedge_symbol", hedge_symbol)
        fixed_beta = params.get("fixed_hedge_ratio", fixed_hedge_ratio)
        if fixed_beta is not None:
            fixed_beta = float(fixed_beta)

        if lookback < 5:
            raise ValueError("lookback_period must be at least 5 bars for statistical validity.")
        if entry_th <= exit_th:
            raise ValueError(f"entry_threshold ({entry_th}) must be greater than exit_threshold ({exit_th}).")

        super().__init__(
            name="PairsTrading",
            symbol=symbol,
            parameters={
                "hedge_symbol": h_sym,
                "lookback_period": lookback,
                "entry_threshold": entry_th,
                "exit_threshold": exit_th,
                "fixed_hedge_ratio": fixed_beta,
            },
        )
        self.hedge_symbol = h_sym
        self.lookback_period = lookback
        self.entry_threshold = entry_th
        self.exit_threshold = exit_th
        self.fixed_hedge_ratio = fixed_beta
        self.hedge_data = hedge_data.copy() if hedge_data is not None else None
        if self.hedge_data is not None:
            self.hedge_data["timestamp"] = pd.to_datetime(self.hedge_data["timestamp"])
            self.hedge_data = self.hedge_data.sort_values(by="timestamp").reset_index(drop=True)

        self.warmup_period = lookback
        self._is_long: bool = False

    def reset(self) -> None:
        self._is_long = False

    @staticmethod
    def estimate_hedge_ratio(p1: pd.Series, p2: pd.Series) -> float:
        """Estimates hedge ratio beta via sample covariance / variance."""
        var_p2 = p2.var(ddof=1)
        if var_p2 <= 1e-8 or pd.isna(var_p2):
            return 1.0
        cov_p1_p2 = p1.cov(p2)
        if pd.isna(cov_p1_p2):
            return 1.0
        return float(cov_p1_p2 / var_p2)

    @staticmethod
    def calculate_spread(p1: pd.Series, p2: pd.Series, beta: float) -> pd.Series:
        return p1 - (beta * p2)

    @staticmethod
    def calculate_z_score(spread_window: pd.Series) -> float:
        mean_s = spread_window.mean()
        std_s = spread_window.std(ddof=1)
        if pd.isna(std_s) or std_s <= 1e-8:
            return 0.0
        return float((spread_window.iloc[-1] - mean_s) / std_s)

    def _get_hedge_series(self, bar: OHLCVBar, history_df: pd.DataFrame) -> Optional[pd.Series]:
        """Extracts aligned hedge asset price series up to current bar."""
        # 1. Check if history_df contains hedge close column
        for candidate_col in ["hedge_close", f"{self.hedge_symbol.lower()}_close", self.hedge_symbol.lower()]:
            if candidate_col in history_df.columns:
                return history_df[candidate_col]

        # 2. Check external hedge_data table aligned by timestamp
        if self.hedge_data is not None:
            sub = self.hedge_data[self.hedge_data["timestamp"] <= bar.timestamp]
            if len(sub) >= len(history_df):
                return sub["close"].iloc[-len(history_df):].reset_index(drop=True)

        return None

    def generate_signal(self, bar: OHLCVBar, history_df: pd.DataFrame) -> Optional[SignalEvent]:
        if len(history_df) < self.warmup_period:
            return None

        p2_series = self._get_hedge_series(bar, history_df)
        if p2_series is None or len(p2_series) < self.warmup_period:
            return None

        # Take matching lookback window
        p1_window = history_df["close"].iloc[-self.lookback_period:].reset_index(drop=True)
        p2_window = p2_series.iloc[-self.lookback_period:].reset_index(drop=True)

        if len(p1_window) != len(p2_window) or p1_window.isna().any() or p2_window.isna().any():
            return None

        # Compute or use fixed hedge ratio
        if self.fixed_hedge_ratio is not None:
            beta = self.fixed_hedge_ratio
        else:
            beta = self.estimate_hedge_ratio(p1_window, p2_window)

        # Spread & z-score
        spread_series = self.calculate_spread(p1_window, p2_window, beta)
        z_score = self.calculate_z_score(spread_series)

        # Entry signal: Spread is undervalued (Asset 1 cheap relative to Asset 2)
        if z_score <= -self.entry_threshold:
            if not self._is_long:
                self._is_long = True
                return SignalEvent(
                    timestamp=bar.timestamp,
                    symbol=self.symbol,
                    signal_type=SignalType.BUY,
                    metadata={
                        "z_score": round(z_score, 4),
                        "hedge_ratio": round(beta, 4),
                        "spread": round(float(spread_series.iloc[-1]), 4),
                        "entry_threshold": self.entry_threshold,
                        "hedge_symbol": self.hedge_symbol,
                    },
                )

        # Exit signal: Spread reverts toward equilibrium
        elif z_score >= -self.exit_threshold:
            if self._is_long:
                self._is_long = False
                return SignalEvent(
                    timestamp=bar.timestamp,
                    symbol=self.symbol,
                    signal_type=SignalType.SELL,
                    metadata={
                        "z_score": round(z_score, 4),
                        "hedge_ratio": round(beta, 4),
                        "spread": round(float(spread_series.iloc[-1]), 4),
                        "exit_threshold": self.exit_threshold,
                        "hedge_symbol": self.hedge_symbol,
                    },
                )

        return None
