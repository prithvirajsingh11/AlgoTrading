"""Chronological dataset splitting and train-only feature scaling for ML.

STRICT DATA LEAKAGE INVARIANTS:
1. Chronological order: Train [0..i1) < Validation [i1..i2) < Test [i2..N).
2. Out-of-sample quarantine: The test set is completely withheld from all
   feature scaling, hyperparameter tuning, and model selection.
3. Feature scalers (StandardScaler / RobustScaler / MinMaxScaler) are fitted
   EXCLUSIVELY on training features (X_train). They are never fitted on validation
   or test data.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np
from backend.app.ml.dataset import MLDataset


@dataclass
class FeatureScaler:
    """Feature normalization fitted strictly on training data."""

    method: str = "standard"  # "standard", "minmax", "none"
    means: Optional[Dict[str, float]] = None
    scales: Optional[Dict[str, float]] = None
    mins: Optional[Dict[str, float]] = None
    maxs: Optional[Dict[str, float]] = None

    def fit(self, X: pd.DataFrame) -> FeatureScaler:
        """Fits scaler parameters strictly on training partition."""
        if self.method == "none":
            return self

        if self.method == "standard":
            self.means = {col: float(X[col].mean()) for col in X.columns}
            # Add small epsilon to avoid divide-by-zero
            self.scales = {col: float(max(X[col].std(), 1e-8)) for col in X.columns}
        elif self.method == "minmax":
            self.mins = {col: float(X[col].min()) for col in X.columns}
            self.maxs = {col: float(X[col].max()) for col in X.columns}
            self.scales = {
                col: float(max(self.maxs[col] - self.mins[col], 1e-8)) for col in X.columns
            }
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Applies fitted scaling parameters to any partition."""
        if self.method == "none" or (self.means is None and self.mins is None):
            return X.copy()

        X_scaled = X.copy()
        if self.method == "standard":
            for col in X.columns:
                mean = self.means.get(col, 0.0)
                scale = self.scales.get(col, 1.0)
                X_scaled[col] = (X[col] - mean) / scale
        elif self.method == "minmax":
            for col in X.columns:
                min_val = self.mins.get(col, 0.0)
                scale = self.scales.get(col, 1.0)
                X_scaled[col] = (X[col] - min_val) / scale
        return X_scaled

    def fit_transform(self, X: pd.DataFrame) -> pd.DataFrame:
        self.fit(X)
        return self.transform(X)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "means": self.means,
            "scales": self.scales,
            "mins": self.mins,
            "maxs": self.maxs,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FeatureScaler:
        return cls(
            method=data.get("method", "standard"),
            means=data.get("means"),
            scales=data.get("scales"),
            mins=data.get("mins"),
            maxs=data.get("maxs"),
        )


@dataclass
class MLSplitResult:
    """Chronologically partitioned and optionally scaled train/val/test splits."""

    X_train: pd.DataFrame
    y_train: pd.Series
    X_val: pd.DataFrame
    y_val: pd.Series
    X_test: pd.DataFrame
    y_test: pd.Series
    timestamps_train: pd.Series
    timestamps_val: pd.Series
    timestamps_test: pd.Series
    train_window: Tuple[str, str]
    val_window: Optional[Tuple[str, str]]
    test_window: Tuple[str, str]
    scaler: FeatureScaler

    def to_dict(self) -> Dict[str, Any]:
        return {
            "train_samples": len(self.X_train),
            "val_samples": len(self.X_val),
            "test_samples": len(self.X_test),
            "train_window": list(self.train_window),
            "val_window": list(self.val_window) if self.val_window else None,
            "test_window": list(self.test_window),
            "scaler_method": self.scaler.method,
        }


class TimeAwareSplitter:
    """Executes strictly chronological splits with zero lookahead and train-only scaling."""

    @staticmethod
    def split(
        dataset: MLDataset,
        train_pct: float = 0.60,
        val_pct: float = 0.20,
        test_pct: float = 0.20,
        scale_method: str = "standard",
    ) -> MLSplitResult:
        """Splits an MLDataset chronologically into Train, Validation, and Test."""
        total = train_pct + val_pct + test_pct
        if abs(total - 1.0) > 1e-4:
            raise ValueError(f"Split percentages must sum to 1.0 (received {total:.4f}).")

        if train_pct <= 0 or test_pct <= 0 or val_pct < 0:
            raise ValueError("Train and Test fractions must be strictly positive.")

        n = len(dataset)
        if n < 10:
            raise ValueError(f"MLDataset must have at least 10 samples to split (received {n}).")

        i1 = int(n * train_pct)
        i2 = int(n * (train_pct + val_pct))

        # Enforce minimum sizes
        if i1 <= 0:
            i1 = 1
        if val_pct > 0 and i2 <= i1:
            i2 = i1 + 1
        if i2 >= n:
            i2 = n - 1

        X = dataset.X
        y = dataset.y
        ts = dataset.timestamps

        X_train_raw = X.iloc[:i1].copy().reset_index(drop=True)
        y_train = y.iloc[:i1].copy().reset_index(drop=True)
        ts_train = ts.iloc[:i1].copy().reset_index(drop=True)

        if val_pct > 0:
            X_val_raw = X.iloc[i1:i2].copy().reset_index(drop=True)
            y_val = y.iloc[i1:i2].copy().reset_index(drop=True)
            ts_val = ts.iloc[i1:i2].copy().reset_index(drop=True)
            val_window: Optional[Tuple[str, str]] = (str(ts_val.iloc[0]), str(ts_val.iloc[-1]))
        else:
            X_val_raw = pd.DataFrame(columns=X.columns)
            y_val = pd.Series(dtype=int)
            ts_val = pd.Series(dtype=str)
            val_window = None

        X_test_raw = X.iloc[i2:].copy().reset_index(drop=True)
        y_test = y.iloc[i2:].copy().reset_index(drop=True)
        ts_test = ts.iloc[i2:].copy().reset_index(drop=True)

        # Chronological assertions (zero temporal overlap)
        train_end = ts_train.iloc[-1]
        test_start = ts_test.iloc[0]
        if val_window:
            val_start = ts_val.iloc[0]
            val_end = ts_val.iloc[-1]
            if train_end >= val_start:
                raise ValueError(f"Temporal leakage detected: Train end ({train_end}) >= Val start ({val_start}).")
            if val_end >= test_start:
                raise ValueError(f"Temporal leakage detected: Val end ({val_end}) >= Test start ({test_start}).")
        else:
            if train_end >= test_start:
                raise ValueError(f"Temporal leakage detected: Train end ({train_end}) >= Test start ({test_start}).")

        # Fit feature scaler ONLY on training features
        scaler = FeatureScaler(method=scale_method)
        X_train = scaler.fit_transform(X_train_raw)
        X_val = scaler.transform(X_val_raw) if not X_val_raw.empty else X_val_raw
        X_test = scaler.transform(X_test_raw)

        return MLSplitResult(
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            X_test=X_test,
            y_test=y_test,
            timestamps_train=ts_train,
            timestamps_val=ts_val,
            timestamps_test=ts_test,
            train_window=(str(ts_train.iloc[0]), str(train_end)),
            val_window=val_window,
            test_window=(str(test_start), str(ts_test.iloc[-1])),
            scaler=scaler,
        )
