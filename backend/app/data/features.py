from typing import Union
import numpy as np
import pandas as pd


def compute_sma(series: pd.Series, window: int) -> pd.Series:
    """Computes Simple Moving Average (SMA)."""
    if window <= 0:
        raise ValueError("Window size must be positive.")
    return series.rolling(window=window, min_periods=window).mean()


def compute_ema(series: pd.Series, span: int) -> pd.Series:
    """Computes Exponential Moving Average (EMA)."""
    if span <= 0:
        raise ValueError("Span must be positive.")
    return series.ewm(span=span, adjust=False).mean()


def compute_returns(series: pd.Series, log: bool = False) -> pd.Series:
    """Computes simple or log percentage returns."""
    if log:
        return np.log(series / series.shift(1))
    return series.pct_change()


def compute_volatility(series: pd.Series, window: int = 20, annualized: bool = True) -> pd.Series:
    """Computes rolling volatility from returns."""
    ret = compute_returns(series)
    vol = ret.rolling(window=window).std()
    if annualized:
        vol = vol * np.sqrt(252)
    return vol
