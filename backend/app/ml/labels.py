"""Target / Label definition for supervised classification models.

CRITICAL INVARIANT:
Future values (close[t + N]) are used EXCLUSIVELY to construct training ground-truth
labels for supervised learning.
Future values and future returns must NEVER be included in model input features.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np


@dataclass
class LabelConfig:
    """Configuration for future return target classification labels."""

    horizon: int = 5          # Number of bars forward into the future (N)
    threshold: float = 0.0    # Minimum future return required to assign positive class (label=1)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LabelConfig:
        return cls(
            horizon=int(data.get("horizon", 5)),
            threshold=float(data.get("threshold", 0.0)),
        )


def compute_future_returns_and_labels(
    df: pd.DataFrame,
    config: Optional[LabelConfig] = None,
) -> pd.DataFrame:
    """Computes future return and binary target classification labels.

    future_return[t] = close[t + N] / close[t] - 1.0
    label[t] = 1 if future_return[t] > threshold else 0

    NOTE: The last N rows of the dataset will naturally contain NaN for future_return
    and label because the future price has not yet unfolded. These rows MUST be dropped
    during training dataset alignment.
    """
    if "close" not in df.columns:
        raise ValueError("DataFrame must contain a 'close' price column to compute future labels.")

    cfg = config or LabelConfig()
    if cfg.horizon <= 0:
        raise ValueError(f"Label horizon must be a positive integer >= 1 (received {cfg.horizon}).")

    close = df["close"].astype(float)
    # Shift backward: close[t + N] aligns at index t
    future_close = close.shift(-cfg.horizon)
    future_return = (future_close / close) - 1.0

    # Binary label: 1 if return strictly exceeds threshold, 0 otherwise
    # Retain NaN for the trailing horizon bars
    labels = pd.Series(np.nan, index=df.index, dtype="float64")
    valid_mask = future_return.notna()
    labels[valid_mask] = (future_return[valid_mask] > cfg.threshold).astype(int)

    out_df = pd.DataFrame(index=df.index)
    out_df["future_return"] = future_return
    out_df["label"] = labels
    return out_df
