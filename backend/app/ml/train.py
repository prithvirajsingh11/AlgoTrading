"""Unified ML training pipeline and chronological Walk-Forward ML engine.

Ensures test sets remain completely untouched during training and feature scaling.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple, List
import pandas as pd
import numpy as np

from backend.app.ml.features import FeatureEngineer, FeatureConfig
from backend.app.ml.labels import LabelConfig
from backend.app.ml.dataset import build_supervised_dataset, MLDataset
from backend.app.ml.split import TimeAwareSplitter, MLSplitResult, FeatureScaler
from backend.app.ml.model import XGBoostModel, XGBoostModelConfig
from backend.app.ml.evaluate import evaluate_classification, ClassificationMetrics
from backend.app.ml.calibration import ProbabilityCalibrator
from backend.app.ml.artifacts import MLModelArtifact
from backend.app.backtesting.walk_forward import WalkForwardEngine


@dataclass
class MLTrainResult:
    """Artifact and multi-split evaluation metrics produced by pipeline."""

    artifact: MLModelArtifact
    train_metrics: ClassificationMetrics
    val_metrics: Optional[ClassificationMetrics]
    test_metrics: ClassificationMetrics
    calibration_report: Optional[Dict[str, Any]]
    dataset_summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact": self.artifact.to_dict(),
            "train_metrics": self.train_metrics.to_dict(),
            "val_metrics": self.val_metrics.to_dict() if self.val_metrics else None,
            "test_metrics": self.test_metrics.to_dict(),
            "calibration_report": self.calibration_report,
            "dataset_summary": self.dataset_summary,
        }


def train_ml_pipeline(
    df: pd.DataFrame,
    feature_config: Optional[FeatureConfig] = None,
    label_config: Optional[LabelConfig] = None,
    model_config: Optional[XGBoostModelConfig] = None,
    train_pct: float = 0.60,
    val_pct: float = 0.20,
    test_pct: float = 0.20,
    scale_method: str = "standard",
    calibration_method: str = "none",
    model_version: str = "v1.0.0",
    symbol: str = "ASSET",
) -> MLTrainResult:
    """Executes full time-series supervised learning pipeline with zero lookahead."""
    fe_cfg = feature_config or FeatureConfig()
    lbl_cfg = label_config or LabelConfig()
    mdl_cfg = model_config or XGBoostModelConfig()

    # 1. Dataset generation & alignment
    fe = FeatureEngineer(fe_cfg)
    dataset = build_supervised_dataset(df, feature_engineer=fe, label_config=lbl_cfg, symbol=symbol)

    # 2. Chronological split (scaler fit ONLY on train)
    splits = TimeAwareSplitter.split(
        dataset=dataset,
        train_pct=train_pct,
        val_pct=val_pct,
        test_pct=test_pct,
        scale_method=scale_method,
    )

    # 3. Model training
    model = XGBoostModel(config=mdl_cfg)
    model.fit(
        X_train=splits.X_train,
        y_train=splits.y_train,
        X_val=splits.X_val if not splits.X_val.empty else None,
        y_val=splits.y_val if not splits.y_val.empty else None,
    )

    # 4. Feature importance
    feature_importance = model.get_feature_importance(importance_type="gain")

    # 5. Evaluate on each partition
    # Train
    train_probs = model.predict_proba(splits.X_train)
    train_preds = model.predict(splits.X_train)
    train_metrics = evaluate_classification(splits.y_train, train_preds, train_probs)

    # Validation
    val_metrics: Optional[ClassificationMetrics] = None
    val_probs: Optional[np.ndarray] = None
    if not splits.X_val.empty:
        val_probs = model.predict_proba(splits.X_val)
        val_preds = model.predict(splits.X_val)
        val_metrics = evaluate_classification(splits.y_val, val_preds, val_probs)

    # Calibration (if requested, fit on validation)
    calibrator = ProbabilityCalibrator(method=calibration_method)
    if val_probs is not None and not splits.X_val.empty:
        calibrator.fit(val_probs[:, 1], splits.y_val.values)
    else:
        calibrator.fit(train_probs[:, 1], splits.y_train.values)

    # Test (strictly out-of-sample)
    test_probs = model.predict_proba(splits.X_test)
    test_preds = model.predict(splits.X_test)
    # Apply calibration to test probs if calibrated
    if calibrator.report and calibrator.report.calibrated:
        test_probs_cal = calibrator.calibrate(test_probs[:, 1])
        test_probs = np.column_stack([1.0 - test_probs_cal, test_probs_cal])

    test_metrics = evaluate_classification(splits.y_test, test_preds, test_probs)

    # 6. Build versioned artifact
    artifact = MLModelArtifact(
        model_json=model.to_json_str(),
        feature_names=list(dataset.feature_names),
        feature_order=list(dataset.feature_names),
        feature_schema_hash=dataset.feature_schema_hash,
        training_config=mdl_cfg.to_dict(),
        label_config=lbl_cfg.to_dict(),
        dataset_metadata=dataset.metadata,
        training_period=splits.train_window,
        val_period=splits.val_window,
        test_period=splits.test_window,
        random_seed=mdl_cfg.random_seed,
        model_version=model_version,
        scaler_state=splits.scaler.to_dict(),
        feature_importance=feature_importance,
        classification_metrics=test_metrics.to_dict(),
    )

    return MLTrainResult(
        artifact=artifact,
        train_metrics=train_metrics,
        val_metrics=val_metrics,
        test_metrics=test_metrics,
        calibration_report=calibrator.report.to_dict() if calibrator.report else None,
        dataset_summary=dataset.to_dict(),
    )


@dataclass
class WalkForwardMLWindowResult:
    """Individual window result in an ML walk-forward cycle."""

    window_id: int
    train_bars: int
    test_bars: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    classification_metrics: ClassificationMetrics
    test_predictions: List[Dict[str, Any]]


@dataclass
class WalkForwardMLResult:
    """Aggregate result across all rolling ML walk-forward windows."""

    symbol: str
    total_windows: int
    windows: List[WalkForwardMLWindowResult]
    aggregate_classification: ClassificationMetrics

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "total_windows": self.total_windows,
            "windows": [
                {
                    "window_id": w.window_id,
                    "train_bars": w.train_bars,
                    "test_bars": w.test_bars,
                    "train_start": w.train_start,
                    "train_end": w.train_end,
                    "test_start": w.test_start,
                    "test_end": w.test_end,
                    "classification_metrics": w.classification_metrics.to_dict(),
                    "test_predictions_count": len(w.test_predictions),
                }
                for w in self.windows
            ],
            "aggregate_classification": self.aggregate_classification.to_dict(),
        }


class WalkForwardMLEngine:
    """Evaluates XGBoost models chronologically across rolling Train -> Test windows."""

    def __init__(
        self,
        symbol: str = "ASSET",
        feature_config: Optional[FeatureConfig] = None,
        label_config: Optional[LabelConfig] = None,
        model_config: Optional[XGBoostModelConfig] = None,
    ):
        self.symbol = symbol
        self.feature_config = feature_config or FeatureConfig()
        self.label_config = label_config or LabelConfig()
        self.model_config = model_config or XGBoostModelConfig()

    def run(
        self,
        df: pd.DataFrame,
        train_bars: int = 100,
        test_bars: int = 30,
        step_bars: int = 30,
    ) -> WalkForwardMLResult:
        """Executes walk-forward training and test evaluations.

        At each window:
        1. Fit XGBoost on [train_start..train_end].
        2. Freeze model.
        3. Evaluate on unseen [test_start..test_end].
        """
        slices = WalkForwardEngine.generate_window_slices(
            total_bars=len(df),
            train_bars=train_bars,
            test_bars=test_bars,
            step_bars=step_bars,
        )

        windows_results: List[WalkForwardMLWindowResult] = []
        all_y_true: List[int] = []
        all_y_pred: List[int] = []
        all_y_prob: List[float] = []

        fe = FeatureEngineer(self.feature_config)

        for win_id, (tr_start, tr_end, te_start, te_end) in enumerate(slices):
            # 1. Slice training data
            train_df = df.iloc[tr_start:tr_end].reset_index(drop=True)
            test_df = df.iloc[te_start:te_end].reset_index(drop=True)

            # Build train dataset
            train_dataset = build_supervised_dataset(
                train_df,
                feature_engineer=fe,
                label_config=self.label_config,
                symbol=self.symbol,
            )

            # Scale strictly on train
            scaler = FeatureScaler(method="standard")
            X_train_scaled = scaler.fit_transform(train_dataset.X)

            # Fit model
            model = XGBoostModel(config=self.model_config)
            model.fit(X_train=X_train_scaled, y_train=train_dataset.y)

            # 2. Build test dataset (out-of-sample)
            # Need slight warmup preceding te_start to generate features for the test bars
            warmup = fe.warmup_bars
            slice_start = max(0, te_start - warmup)
            test_full_slice = df.iloc[slice_start:te_end].reset_index(drop=True)

            test_dataset = build_supervised_dataset(
                test_full_slice,
                feature_engineer=fe,
                label_config=self.label_config,
                symbol=self.symbol,
            )

            # Align only to the true test timestamps
            test_ts_set = set(test_df["timestamp"].astype(str))
            mask = test_dataset.timestamps.isin(test_ts_set)
            if not mask.any():
                continue

            X_test = test_dataset.X[mask].reset_index(drop=True)
            y_test = test_dataset.y[mask].reset_index(drop=True)
            ts_test = test_dataset.timestamps[mask].reset_index(drop=True)

            # Scale test using train-fitted scaler
            X_test_scaled = scaler.transform(X_test)

            # Predict
            probs = model.predict_proba(X_test_scaled)
            preds = model.predict(X_test_scaled)

            win_metrics = evaluate_classification(y_test, preds, probs)

            pred_records: List[Dict[str, Any]] = []
            for i in range(len(X_test)):
                pred_records.append({
                    "timestamp": str(ts_test.iloc[i]),
                    "y_true": int(y_test.iloc[i]),
                    "y_pred": int(preds[i]),
                    "prob_positive": round(float(probs[i, 1]), 4),
                })
                all_y_true.append(int(y_test.iloc[i]))
                all_y_pred.append(int(preds[i]))
                all_y_prob.append(float(probs[i, 1]))

            windows_results.append(
                WalkForwardMLWindowResult(
                    window_id=win_id,
                    train_bars=len(X_train_scaled),
                    test_bars=len(X_test),
                    train_start=str(train_dataset.timestamps.iloc[0]),
                    train_end=str(train_dataset.timestamps.iloc[-1]),
                    test_start=str(ts_test.iloc[0]),
                    test_end=str(ts_test.iloc[-1]),
                    classification_metrics=win_metrics,
                    test_predictions=pred_records,
                )
            )

        # Aggregate across all test windows
        agg_metrics = evaluate_classification(
            np.array(all_y_true),
            np.array(all_y_pred),
            np.array(all_y_prob),
        )

        return WalkForwardMLResult(
            symbol=self.symbol,
            total_windows=len(windows_results),
            windows=windows_results,
            aggregate_classification=agg_metrics,
        )
