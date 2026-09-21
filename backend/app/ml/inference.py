"""Inference layer producing structured prediction outputs.

Validates feature schema and normalizes features before model prediction.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from backend.app.ml.artifacts import MLModelArtifact
from backend.app.ml.model import XGBoostModel
from backend.app.ml.split import FeatureScaler


@dataclass
class MLPrediction:
    """Structured, probability-rich ML prediction object."""

    timestamp: str
    symbol: str
    predicted_class: int
    probability_positive: float
    probability_negative: float
    model_version: str
    feature_schema_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MLPredictor:
    """Coordinates schema validation, scaling, and XGBoost inference."""

    def __init__(self, artifact: MLModelArtifact):
        self.artifact = artifact
        self.model: XGBoostModel = artifact.get_model()
        self.scaler: FeatureScaler = artifact.get_scaler()

    def predict_bar(
        self,
        features_df: pd.DataFrame,
        timestamp: str,
        symbol: str,
    ) -> MLPrediction:
        """Predicts directional probability for a single bar feature row."""
        if features_df.empty:
            raise ValueError("Empty feature DataFrame supplied for inference.")

        # 1. Schema validation
        incoming_cols = list(features_df.columns)
        self.artifact.validate_feature_schema(incoming_cols)

        # 2. Scale features using train-fitted scaler
        X_scaled = self.scaler.transform(features_df)

        # 3. Model inference
        probs = self.model.predict_proba(X_scaled)
        p_neg = float(probs[0, 0])
        p_pos = float(probs[0, 1])

        pred_class = 1 if p_pos >= 0.5 else 0

        return MLPrediction(
            timestamp=str(timestamp),
            symbol=symbol,
            predicted_class=pred_class,
            probability_positive=round(p_pos, 4),
            probability_negative=round(p_neg, 4),
            model_version=self.artifact.model_version,
            feature_schema_hash=self.artifact.feature_schema_hash,
        )

    def predict_batch(
        self,
        features_df: pd.DataFrame,
        timestamps: List[str],
        symbol: str,
    ) -> List[MLPrediction]:
        """Predicts directional probabilities for a batch of historical feature rows."""
        if features_df.empty:
            return []

        # 1. Schema validation
        incoming_cols = list(features_df.columns)
        self.artifact.validate_feature_schema(incoming_cols)

        # 2. Scale
        X_scaled = self.scaler.transform(features_df)

        # 3. Model inference
        probs = self.model.predict_proba(X_scaled)

        preds: List[MLPrediction] = []
        for i in range(len(features_df)):
            p_neg = float(probs[i, 0])
            p_pos = float(probs[i, 1])
            pred_class = 1 if p_pos >= 0.5 else 0
            ts = timestamps[i] if i < len(timestamps) else ""
            preds.append(
                MLPrediction(
                    timestamp=str(ts),
                    symbol=symbol,
                    predicted_class=pred_class,
                    probability_positive=round(p_pos, 4),
                    probability_negative=round(p_neg, 4),
                    model_version=self.artifact.model_version,
                    feature_schema_hash=self.artifact.feature_schema_hash,
                )
            )
        return preds
