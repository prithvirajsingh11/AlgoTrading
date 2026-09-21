"""Feature engineering pipeline for supervised machine learning models.

CRITICAL INVARIANT:
Every feature at timestamp t depends strictly and exclusively on price/volume
information available at or before timestamp t.
Zero future data, zero forward-peeking lookahead bias.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import pandas as pd


# Feature availability documentation registry
# Categorization:
#   - 'current_bar': uses High, Low, Open, Close of current bar t (intrabar relationship)
#   - 'lagged': direct prior-bar shift or relative delta from t-1 to t
#   - 'rolling': rolling statistical aggregate or recursive filter strictly over window [t-k+1 ... t]
FEATURE_METADATA: Dict[str, Dict[str, str]] = {
    "log_return": {
        "type": "lagged",
        "description": "Logarithmic price return from bar t-1 to bar t",
        "formula": "ln(Close[t] / Close[t-1])",
    },
    "simple_return": {
        "type": "lagged",
        "description": "Simple percentage price return from bar t-1 to bar t",
        "formula": "(Close[t] - Close[t-1]) / Close[t-1]",
    },
    "sma_distance_10": {
        "type": "rolling",
        "description": "Normalized percentage distance from 10-period Simple Moving Average",
        "formula": "(Close[t] - SMA_10[t]) / SMA_10[t]",
    },
    "sma_distance_20": {
        "type": "rolling",
        "description": "Normalized percentage distance from 20-period Simple Moving Average",
        "formula": "(Close[t] - SMA_20[t]) / SMA_20[t]",
    },
    "sma_distance_50": {
        "type": "rolling",
        "description": "Normalized percentage distance from 50-period Simple Moving Average",
        "formula": "(Close[t] - SMA_50[t]) / SMA_50[t]",
    },
    "ema_distance_10": {
        "type": "rolling",
        "description": "Normalized percentage distance from 10-period Exponential Moving Average",
        "formula": "(Close[t] - EMA_10[t]) / EMA_10[t]",
    },
    "ema_distance_20": {
        "type": "rolling",
        "description": "Normalized percentage distance from 20-period Exponential Moving Average",
        "formula": "(Close[t] - EMA_20[t]) / EMA_20[t]",
    },
    "rsi_14": {
        "type": "rolling",
        "description": "14-period Relative Strength Index oscillator (0-100)",
        "formula": "100 - (100 / (1 + RS)) strictly on slice 0..t",
    },
    "macd": {
        "type": "rolling",
        "description": "Moving Average Convergence Divergence line normalized by price",
        "formula": "(EMA_12[t] - EMA_26[t]) / Close[t]",
    },
    "macd_signal": {
        "type": "rolling",
        "description": "9-period EMA signal line of MACD normalized by price",
        "formula": "EMA_9(MACD)[t] / Close[t]",
    },
    "macd_hist": {
        "type": "rolling",
        "description": "Normalized MACD Histogram divergence",
        "formula": "MACD[t] - MACD_Signal[t]",
    },
    "atr_14": {
        "type": "rolling",
        "description": "Normalized 14-period Average True Range",
        "formula": "ATR_14[t] / Close[t]",
    },
    "rolling_volatility_20": {
        "type": "rolling",
        "description": "Annualized rolling standard deviation of 20-bar log returns",
        "formula": "std(log_return[t-19..t]) * sqrt(252)",
    },
    "rolling_volume_ratio_20": {
        "type": "rolling",
        "description": "Current volume normalized by 20-period rolling volume average",
        "formula": "Volume[t] / SMA_20(Volume)[t]",
    },
    "rolling_volume_std_20": {
        "type": "rolling",
        "description": "20-period volume dispersion ratio",
        "formula": "std(Volume[t-19..t]) / (mean(Volume[t-19..t]) + 1e-8)",
    },
    "price_momentum_5": {
        "type": "rolling",
        "description": "5-bar cumulative price momentum",
        "formula": "Close[t] / Close[t-5] - 1.0",
    },
    "price_momentum_10": {
        "type": "rolling",
        "description": "10-bar cumulative price momentum",
        "formula": "Close[t] / Close[t-10] - 1.0",
    },
    "high_low_range": {
        "type": "current_bar",
        "description": "Intrabar high-low spread normalized by close",
        "formula": "(High[t] - Low[t]) / Close[t]",
    },
    "close_open_range": {
        "type": "current_bar",
        "description": "Intrabar directional move normalized by open",
        "formula": "(Close[t] - Open[t]) / Open[t]",
    },
}


@dataclass
class FeatureConfig:
    """Configuration for technical indicator feature generator."""

    sma_windows: Tuple[int, ...] = (10, 20, 50)
    ema_windows: Tuple[int, ...] = (10, 20)
    rsi_window: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    atr_window: int = 14
    volatility_window: int = 20
    volume_window: int = 20
    momentum_windows: Tuple[int, ...] = (5, 10)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sma_windows": list(self.sma_windows),
            "ema_windows": list(self.ema_windows),
            "rsi_window": self.rsi_window,
            "macd_fast": self.macd_fast,
            "macd_slow": self.macd_slow,
            "macd_signal": self.macd_signal,
            "atr_window": self.atr_window,
            "volatility_window": self.volatility_window,
            "volume_window": self.volume_window,
            "momentum_windows": list(self.momentum_windows),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FeatureConfig:
        return cls(
            sma_windows=tuple(data.get("sma_windows", [10, 20, 50])),
            ema_windows=tuple(data.get("ema_windows", [10, 20])),
            rsi_window=int(data.get("rsi_window", 14)),
            macd_fast=int(data.get("macd_fast", 12)),
            macd_slow=int(data.get("macd_slow", 26)),
            macd_signal=int(data.get("macd_signal", 9)),
            atr_window=int(data.get("atr_window", 14)),
            volatility_window=int(data.get("volatility_window", 20)),
            volume_window=int(data.get("volume_window", 20)),
            momentum_windows=tuple(data.get("momentum_windows", [5, 10])),
        )


class FeatureEngineer:
    """Generates machine learning features strictly without lookahead bias."""

    def __init__(self, config: Optional[FeatureConfig] = None):
        self.config = config or FeatureConfig()

    @property
    def warmup_bars(self) -> int:
        """Calculates minimum historical bars needed before features become reliable."""
        max_sma = max(self.config.sma_windows) if self.config.sma_windows else 20
        max_mom = max(self.config.momentum_windows) if self.config.momentum_windows else 10
        return max(max_sma, self.config.macd_slow + self.config.macd_signal, self.config.volatility_window, max_mom, self.config.atr_window) + 5

    def compute_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Vectorized feature computation on historical OHLCV data.

        Guarantees that at each row i, all values are computed strictly from
        rows 0 to i.
        """
        required_cols = {"open", "high", "low", "close", "volume"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns for feature engineering: {sorted(missing)}")

        if df.empty:
            return pd.DataFrame()

        close = df["close"].astype(float)
        open_ = df["open"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        vol = df["volume"].astype(float)

        feats = pd.DataFrame(index=df.index)

        # 1. Returns
        log_ret = np.log(close / close.shift(1))
        feats["log_return"] = log_ret
        feats["simple_return"] = close.pct_change(1)

        # 2. SMA Distances
        for w in self.config.sma_windows:
            sma = close.rolling(window=w, min_periods=w).mean()
            feats[f"sma_distance_{w}"] = (close - sma) / sma

        # 3. EMA Distances
        for w in self.config.ema_windows:
            ema = close.ewm(span=w, adjust=False).mean()
            feats[f"ema_distance_{w}"] = (close - ema) / ema

        # 4. RSI
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=self.config.rsi_window, min_periods=self.config.rsi_window).mean()
        avg_loss = loss.rolling(window=self.config.rsi_window, min_periods=self.config.rsi_window).mean()
        rs = avg_gain / (avg_loss + 1e-9)
        feats[f"rsi_{self.config.rsi_window}"] = 100.0 - (100.0 / (1.0 + rs))

        # 5. MACD
        ema_fast = close.ewm(span=self.config.macd_fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.config.macd_slow, adjust=False).mean()
        raw_macd = ema_fast - ema_slow
        raw_signal = raw_macd.ewm(span=self.config.macd_signal, adjust=False).mean()
        feats["macd"] = raw_macd / close
        feats["macd_signal"] = raw_signal / close
        feats["macd_hist"] = (raw_macd - raw_signal) / close

        # 6. ATR
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.config.atr_window, min_periods=self.config.atr_window).mean()
        feats[f"atr_{self.config.atr_window}"] = atr / close

        # 7. Rolling Volatility
        vol_roll = log_ret.rolling(window=self.config.volatility_window, min_periods=self.config.volatility_window).std()
        feats[f"rolling_volatility_{self.config.volatility_window}"] = vol_roll * np.sqrt(252.0)

        # 8. Rolling Volume Statistics
        vol_mean = vol.rolling(window=self.config.volume_window, min_periods=self.config.volume_window).mean()
        vol_std = vol.rolling(window=self.config.volume_window, min_periods=self.config.volume_window).std()
        feats[f"rolling_volume_ratio_{self.config.volume_window}"] = vol / (vol_mean + 1e-9)
        feats[f"rolling_volume_std_{self.config.volume_window}"] = vol_std / (vol_mean + 1e-9)

        # 9. Momentum
        for m in self.config.momentum_windows:
            feats[f"price_momentum_{m}"] = close / close.shift(m) - 1.0

        # 10. Intrabar Ranges
        feats["high_low_range"] = (high - low) / close
        feats["close_open_range"] = (close - open_) / open_

        return feats

    def compute_bar_features(self, history_df: pd.DataFrame) -> pd.DataFrame:
        """Computes feature vector for the latest bar given historical slice 0..t."""
        full_feats = self.compute_features(history_df)
        if full_feats.empty:
            return pd.DataFrame()
        return full_feats.iloc[[-1]].copy()
