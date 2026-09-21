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

from typing import Dict, Any, Optional, Union, List, Tuple
import numpy as np
import pandas as pd
from backend.app.strategies.base import BaseStrategy
from backend.app.data.loader import OHLCVBar, MarketSnapshot
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
        two_leg: bool = False,
        use_log_prices: bool = False,
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
        is_two_leg = bool(params.get("two_leg", two_leg))
        use_log = bool(params.get("use_log_prices", use_log_prices))

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
                "two_leg": is_two_leg,
                "use_log_prices": use_log,
            },
        )
        self.hedge_symbol = h_sym
        self.lookback_period = lookback
        self.entry_threshold = entry_th
        self.exit_threshold = exit_th
        self.fixed_hedge_ratio = fixed_beta
        self.two_leg = is_two_leg
        self.use_log_prices = use_log
        self.hedge_data = hedge_data.copy() if hedge_data is not None else None
        if self.hedge_data is not None:
            self.hedge_data["timestamp"] = pd.to_datetime(self.hedge_data["timestamp"])
            self.hedge_data = self.hedge_data.sort_values(by="timestamp").reset_index(drop=True)

        self.warmup_period = lookback
        self._is_long: bool = False
        self._position_state: Optional[str] = None  # None, "LONG_SPREAD", or "SHORT_SPREAD"

    def reset(self) -> None:
        self._is_long = False
        self._position_state = None

    @staticmethod
    def estimate_hedge_ratio(p1: pd.Series, p2: pd.Series, use_log: bool = False) -> float:
        """Estimates hedge ratio beta via sample covariance / variance."""
        s1 = np.log(p1) if use_log else p1
        s2 = np.log(p2) if use_log else p2
        var_s2 = s2.var(ddof=1)
        if var_s2 <= 1e-8 or pd.isna(var_s2):
            return 1.0
        cov_s1_s2 = s1.cov(s2)
        if pd.isna(cov_s1_s2):
            return 1.0
        return float(cov_s1_s2 / var_s2)

    @staticmethod
    def calculate_spread(p1: pd.Series, p2: pd.Series, beta: float, use_log: bool = False) -> pd.Series:
        s1 = np.log(p1) if use_log else p1
        s2 = np.log(p2) if use_log else p2
        return s1 - (beta * s2)

    @staticmethod
    def calculate_z_score(spread_window: pd.Series) -> float:
        mean_s = spread_window.mean()
        std_s = spread_window.std(ddof=1)
        if pd.isna(std_s) or std_s <= 1e-8:
            return 0.0
        return float((spread_window.iloc[-1] - mean_s) / std_s)

    def _extract_series(
        self,
        bar: Union[OHLCVBar, MarketSnapshot],
        history_df: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
    ) -> Tuple[Optional[pd.Series], Optional[pd.Series]]:
        """Extracts aligned price series for symbol and hedge_symbol up to current bar."""
        ts = bar.timestamp
        if isinstance(history_df, dict):
            df_a = history_df.get(self.symbol)
            df_b = history_df.get(self.hedge_symbol)
            if df_a is None or df_b is None:
                return None, None
            s_a = df_a[df_a["timestamp"] <= ts]["close"].reset_index(drop=True)
            s_b = df_b[df_b["timestamp"] <= ts]["close"].reset_index(drop=True)
            return s_a, s_b

        sub_df = history_df[history_df["timestamp"] <= ts] if "timestamp" in history_df.columns else history_df
        s_a = sub_df["close"].reset_index(drop=True) if "close" in sub_df.columns else None

        s_b = None
        for candidate_col in ["hedge_close", f"{self.hedge_symbol.lower()}_close", self.hedge_symbol.lower()]:
            if candidate_col in sub_df.columns:
                s_b = sub_df[candidate_col].reset_index(drop=True)
                break

        if s_b is None and self.hedge_data is not None:
            sub = self.hedge_data[self.hedge_data["timestamp"] <= ts]
            if len(sub) >= len(sub_df):
                s_b = sub["close"].iloc[-len(sub_df):].reset_index(drop=True)

        return s_a, s_b

    def generate_signal(
        self,
        bar: Union[OHLCVBar, MarketSnapshot],
        history_df: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
    ) -> Optional[Union[SignalEvent, List[SignalEvent]]]:
        p1_series, p2_series = self._extract_series(bar, history_df)
        if p1_series is None or p2_series is None:
            return None
        if len(p1_series) < self.warmup_period or len(p2_series) < self.warmup_period:
            return None

        p1_window = p1_series.iloc[-self.lookback_period:].reset_index(drop=True)
        p2_window = p2_series.iloc[-self.lookback_period:].reset_index(drop=True)

        if len(p1_window) != len(p2_window) or p1_window.isna().any() or p2_window.isna().any():
            return None

        if self.fixed_hedge_ratio is not None:
            beta = self.fixed_hedge_ratio
        else:
            beta = self.estimate_hedge_ratio(p1_window, p2_window, use_log=self.use_log_prices)

        spread_series = self.calculate_spread(p1_window, p2_window, beta, use_log=self.use_log_prices)
        z_score = self.calculate_z_score(spread_series)

        is_two_leg = self.two_leg or isinstance(bar, MarketSnapshot)

        meta = {
            "z_score": round(z_score, 4),
            "hedge_ratio": round(beta, 4),
            "spread": round(float(spread_series.iloc[-1]), 4),
            "entry_threshold": self.entry_threshold,
            "exit_threshold": self.exit_threshold,
            "hedge_symbol": self.hedge_symbol,
            "hedge_qty_ratio": round(beta, 4),
        }

        if is_two_leg:
            # 1. Long Spread (z <= -entry_threshold): BUY Asset A, SELL Asset B
            if z_score <= -self.entry_threshold:
                if self._position_state != "LONG_SPREAD":
                    self._position_state = "LONG_SPREAD"
                    return [
                        SignalEvent(timestamp=bar.timestamp, symbol=self.symbol, signal_type=SignalType.BUY, metadata=meta),
                        SignalEvent(timestamp=bar.timestamp, symbol=self.hedge_symbol, signal_type=SignalType.SELL, metadata=meta),
                    ]
            # 2. Short Spread (z >= entry_threshold): SELL Asset A, BUY Asset B
            elif z_score >= self.entry_threshold:
                if self._position_state != "SHORT_SPREAD":
                    self._position_state = "SHORT_SPREAD"
                    return [
                        SignalEvent(timestamp=bar.timestamp, symbol=self.symbol, signal_type=SignalType.SELL, metadata=meta),
                        SignalEvent(timestamp=bar.timestamp, symbol=self.hedge_symbol, signal_type=SignalType.BUY, metadata=meta),
                    ]
            # 3. Exit Spread (|z| <= exit_threshold or crossed back through equilibrium boundary): Exit both legs
            elif (
                (self._position_state == "LONG_SPREAD" and (abs(z_score) <= self.exit_threshold or z_score >= -self.exit_threshold))
                or (self._position_state == "SHORT_SPREAD" and (abs(z_score) <= self.exit_threshold or z_score <= self.exit_threshold))
            ):
                if self._position_state == "LONG_SPREAD":
                    self._position_state = None
                    return [
                        SignalEvent(timestamp=bar.timestamp, symbol=self.symbol, signal_type=SignalType.SELL, metadata=meta),
                        SignalEvent(timestamp=bar.timestamp, symbol=self.hedge_symbol, signal_type=SignalType.BUY, metadata=meta),
                    ]
                elif self._position_state == "SHORT_SPREAD":
                    self._position_state = None
                    return [
                        SignalEvent(timestamp=bar.timestamp, symbol=self.symbol, signal_type=SignalType.BUY, metadata=meta),
                        SignalEvent(timestamp=bar.timestamp, symbol=self.hedge_symbol, signal_type=SignalType.SELL, metadata=meta),
                    ]
            return None

        # Legacy Single-Leg Mode:
        if z_score <= -self.entry_threshold:
            if not self._is_long:
                self._is_long = True
                return SignalEvent(timestamp=bar.timestamp, symbol=self.symbol, signal_type=SignalType.BUY, metadata=meta)
        elif z_score >= -self.exit_threshold:
            if self._is_long:
                self._is_long = False
                return SignalEvent(timestamp=bar.timestamp, symbol=self.symbol, signal_type=SignalType.SELL, metadata=meta)

        return None
