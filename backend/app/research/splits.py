"""Chronological dataset splitting utilities and overfitting safeguards.

Guarantees strict temporal separation:
  TRAIN -> VALIDATION -> TEST
No shuffling, no temporal leakage, and strict out-of-sample quarantine.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, Dict, Any
import pandas as pd


@dataclass
class SplitResult:
    """Represents strictly partitioned chronological datasets."""

    train_df: pd.DataFrame
    val_df: pd.DataFrame
    test_df: pd.DataFrame
    train_bars: int
    val_bars: int
    test_bars: int
    train_start: str
    train_end: str
    val_start: str
    val_end: str
    test_start: str
    test_end: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "train_bars": self.train_bars,
            "val_bars": self.val_bars,
            "test_bars": self.test_bars,
            "train_window": [self.train_start, self.train_end],
            "val_window": [self.val_start, self.val_end],
            "test_window": [self.test_start, self.test_end],
        }


def chronological_split(
    df: pd.DataFrame,
    train_pct: float = 0.60,
    val_pct: float = 0.20,
    test_pct: float = 0.20,
) -> SplitResult:
    """Partitions a historical time series into chronological Train, Validation, and Test sets.

    Strictly preserves temporal sequence:
      Indices: [0 ... i1) -> Train
               [i1 ... i2) -> Validation
               [i2 ... N)  -> Test
    Raises ValueError if fractions do not sum to 1.0 or if observations are insufficient.
    """
    total_pct = train_pct + val_pct + test_pct
    if abs(total_pct - 1.0) > 1e-4:
        raise ValueError(f"Split percentages must sum to 1.0 (received {total_pct:.4f}).")

    if train_pct <= 0 or val_pct < 0 or test_pct <= 0:
        raise ValueError("Train and Test percentages must be strictly positive.")

    if df is None or len(df) < 5:
        raise ValueError("DataFrame must contain at least 5 observations to split.")

    # 1. Ensure strictly sorted by timestamp
    df_sorted = df.copy()
    df_sorted["timestamp"] = pd.to_datetime(df_sorted["timestamp"])
    df_sorted = df_sorted.sort_values(by="timestamp").reset_index(drop=True)

    n = len(df_sorted)
    i1 = int(n * train_pct)
    i2 = int(n * (train_pct + val_pct))

    # Guardrails: ensure each active partition has at least 1 bar
    if i1 <= 0:
        i1 = 1
    if val_pct > 0 and i2 <= i1:
        i2 = i1 + 1
    if i2 >= n:
        i2 = n - 1

    train_df = df_sorted.iloc[:i1].reset_index(drop=True)
    val_df = df_sorted.iloc[i1:i2].reset_index(drop=True) if val_pct > 0 else pd.DataFrame(columns=df_sorted.columns)
    test_df = df_sorted.iloc[i2:].reset_index(drop=True)

    # 2. Strict chronological verification & zero-leakage check
    train_end = train_df["timestamp"].max()
    test_start = test_df["timestamp"].min()

    if not val_df.empty:
        val_start = val_df["timestamp"].min()
        val_end = val_df["timestamp"].max()
        if train_end >= val_start:
            raise ValueError(f"Temporal leakage detected: Train end ({train_end}) >= Val start ({val_start}).")
        if val_end >= test_start:
            raise ValueError(f"Temporal leakage detected: Val end ({val_end}) >= Test start ({test_start}).")
    else:
        val_start, val_end = train_end, train_end
        if train_end >= test_start:
            raise ValueError(f"Temporal leakage detected: Train end ({train_end}) >= Test start ({test_start}).")

    return SplitResult(
        train_df=train_df,
        val_df=val_df,
        test_df=test_df,
        train_bars=len(train_df),
        val_bars=len(val_df),
        test_bars=len(test_df),
        train_start=train_df["timestamp"].min().isoformat(),
        train_end=train_end.isoformat(),
        val_start=val_start.isoformat() if not val_df.empty else "",
        val_end=val_end.isoformat() if not val_df.empty else "",
        test_start=test_start.isoformat(),
        test_end=test_df["timestamp"].max().isoformat(),
    )
