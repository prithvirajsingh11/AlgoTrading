"""Supervised machine learning module using XGBoost for AlgoTrade.

Provides:
- Zero-lookahead feature engineering (FeatureEngineer, FeatureConfig)
- Configurable target labels (LabelConfig, compute_future_returns_and_labels)
- Supervised dataset creation (MLDataset, build_supervised_dataset)
- Time-aware chronological splitting & scaling (TimeAwareSplitter, FeatureScaler)
- Configurable XGBoost classification (XGBoostModel, XGBoostModelConfig)
- Probability calibration (ProbabilityCalibrator)
- Classification metrics (ClassificationMetrics, evaluate_classification)
- Model artifact serialization with schema validation (MLModelArtifact)
- Prediction output (MLPrediction, MLPredictor)
- Training pipeline & Walk-Forward ML (train_ml_pipeline, WalkForwardMLEngine)
"""

from backend.app.ml.features import FeatureEngineer, FeatureConfig, FEATURE_METADATA
from backend.app.ml.labels import LabelConfig, compute_future_returns_and_labels
from backend.app.ml.dataset import MLDataset, build_supervised_dataset, compute_schema_hash
from backend.app.ml.split import TimeAwareSplitter, FeatureScaler, MLSplitResult
from backend.app.ml.model import XGBoostModel, XGBoostModelConfig
from backend.app.ml.evaluate import ClassificationMetrics, evaluate_classification
from backend.app.ml.calibration import ProbabilityCalibrator, CalibrationReport
from backend.app.ml.artifacts import MLModelArtifact
from backend.app.ml.inference import MLPrediction, MLPredictor
from backend.app.ml.train import (
    train_ml_pipeline,
    MLTrainResult,
    WalkForwardMLEngine,
    WalkForwardMLResult,
    WalkForwardMLWindowResult,
)

__all__ = [
    "FeatureEngineer",
    "FeatureConfig",
    "FEATURE_METADATA",
    "LabelConfig",
    "compute_future_returns_and_labels",
    "MLDataset",
    "build_supervised_dataset",
    "compute_schema_hash",
    "TimeAwareSplitter",
    "FeatureScaler",
    "MLSplitResult",
    "XGBoostModel",
    "XGBoostModelConfig",
    "ClassificationMetrics",
    "evaluate_classification",
    "ProbabilityCalibrator",
    "CalibrationReport",
    "MLModelArtifact",
    "MLPrediction",
    "MLPredictor",
    "train_ml_pipeline",
    "MLTrainResult",
    "WalkForwardMLEngine",
    "WalkForwardMLResult",
    "WalkForwardMLWindowResult",
]
