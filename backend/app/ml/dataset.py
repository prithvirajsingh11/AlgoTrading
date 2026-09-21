"""Supervised dataset creation and chronological alignment for ML models.

Transforms raw historical OHLCV data into aligned feature matrices X and label
vectors y, strictly preserving chronological order and trimming indicator warmup
and future-label horizon NaNs.
"""

from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np

from backend.app.ml.features import FeatureEngineer, FeatureConfig
from backend.app.ml.labels import compute_future_returns_and_labels, LabelConfig


@dataclass
class MLDataset:
    """Encapsulates an aligned time-series feature matrix X and target vector y."""

    X: pd.DataFrame
    y: pd.Series
    timestamps: pd.Series
    symbol: str
    feature_names: List[str]
    feature_schema_hash: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.X)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "sample_count": len(self.X),
            "feature_count": len(self.feature_names),
            "feature_names": self.feature_names,
            "feature_schema_hash": self.feature_schema_hash,
            "metadata": self.metadata,
        }


def compute_schema_hash(feature_names: List[str]) -> str:
    """Computes deterministic 64-char SHA-256 hash of ordered feature names."""
    canonical = json.dumps(list(feature_names), separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_supervised_dataset(
    df: pd.DataFrame,
    feature_engineer: Optional[FeatureEngineer] = None,
    label_config: Optional[LabelConfig] = None,
    symbol: str = "ASSET",
) -> MLDataset:
    """Builds a strictly chronological, supervised ML dataset from historical OHLCV bars.

    Process:
    1. Sorts chronologically by timestamp.
    2. Computes technical indicator features strictly over [0..t].
    3. Computes forward-looking classification labels [t+1..t+N].
    4. Drops warmup NaNs and trailing horizon NaNs.
    5. Returns aligned MLDataset with feature schema hash.
    """
    if df is None or len(df) < 20:
        raise ValueError("Historical dataframe must contain at least 20 bars to build an ML dataset.")

    fe = feature_engineer or FeatureEngineer()
    lc = label_config or LabelConfig()

    # 1. Ensure chronological order
    df_sorted = df.copy()
    if "timestamp" in df_sorted.columns:
        df_sorted["timestamp"] = pd.to_datetime(df_sorted["timestamp"])
        df_sorted = df_sorted.sort_values(by="timestamp").reset_index(drop=True)
    else:
        raise ValueError("DataFrame must contain a 'timestamp' column.")

    # 2. Features (using strictly past information 0..t)
    features_df = fe.compute_features(df_sorted)

    # 3. Labels (using future close prices t+N for training target)
    labels_df = compute_future_returns_and_labels(df_sorted, config=lc)

    # 4. Strict Alignment & NaN Trimming
    # Warmup NaNs in features + Trailing NaNs in labels
    valid_mask = features_df.notna().all(axis=1) & labels_df["label"].notna()

    if not valid_mask.any():
        raise ValueError("No valid aligned rows remaining after trimming warmup and label horizon.")

    X_aligned = features_df[valid_mask].copy().reset_index(drop=True)
    y_aligned = labels_df.loc[valid_mask, "label"].astype(int).copy().reset_index(drop=True)
    timestamps_aligned = df_sorted.loc[valid_mask, "timestamp"].astype(str).copy().reset_index(drop=True)

    if len(X_aligned) < 10:
        raise ValueError(f"Insufficient aligned observations ({len(X_aligned)}) to form ML dataset (minimum 10).")

    feature_names = list(X_aligned.columns)
    schema_hash = compute_schema_hash(feature_names)

    pos_count = int((y_aligned == 1).sum())
    neg_count = int((y_aligned == 0).sum())
    pos_ratio = float(pos_count / len(y_aligned)) if len(y_aligned) > 0 else 0.0

    metadata = {
        "symbol": symbol,
        "raw_bars": len(df_sorted),
        "aligned_bars": len(X_aligned),
        "start_timestamp": str(timestamps_aligned.iloc[0]),
        "end_timestamp": str(timestamps_aligned.iloc[-1]),
        "positive_class_count": pos_count,
        "negative_class_count": neg_count,
        "positive_class_ratio": round(pos_ratio, 4),
        "label_horizon": lc.horizon,
        "label_threshold": lc.threshold,
    }

    return MLDataset(
        X=X_aligned,
        y=y_aligned,
        timestamps=timestamps_aligned,
        symbol=symbol,
        feature_names=feature_names,
        feature_schema_hash=schema_hash,
        metadata=metadata,
    )
