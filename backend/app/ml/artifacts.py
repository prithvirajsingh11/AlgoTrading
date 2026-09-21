"""Versioned machine learning model artifacts and feature schema validation.

Guarantees that models cannot be queried with mismatched feature sets or differing
column orderings.
"""

from __future__ import annotations
import json
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from backend.app.ml.model import XGBoostModel, XGBoostModelConfig
from backend.app.ml.split import FeatureScaler


@dataclass
class MLModelArtifact:
    """Self-contained, versioned machine learning model artifact."""

    model_json: str
    feature_names: List[str]
    feature_order: List[str]
    feature_schema_hash: str
    training_config: Dict[str, Any]
    label_config: Dict[str, Any]
    dataset_metadata: Dict[str, Any]
    training_period: Tuple[str, str]
    val_period: Optional[Tuple[str, str]]
    test_period: Optional[Tuple[str, str]]
    random_seed: int
    model_version: str = "v1.0.0"
    scaler_state: Optional[Dict[str, Any]] = None
    feature_importance: Dict[str, float] = field(default_factory=dict)
    classification_metrics: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def validate_feature_schema(self, incoming_features: List[str]) -> None:
        """Validates that incoming features strictly match the trained schema and order.

        Raises ValueError on any schema mismatch.
        """
        if list(incoming_features) != list(self.feature_order):
            missing = set(self.feature_order) - set(incoming_features)
            extra = set(incoming_features) - set(self.feature_order)
            diff_order = [
                f"expected '{e}' at pos {i} but got '{a}'"
                for i, (e, a) in enumerate(zip(self.feature_order, incoming_features))
                if e != a
            ]
            err_msg = (
                f"Feature schema mismatch for model '{self.model_version}'. "
                f"Missing: {sorted(missing)}, Extra: {sorted(extra)}, Ordering: {diff_order[:3]}"
            )
            raise ValueError(err_msg)

    def get_model(self) -> XGBoostModel:
        """Reconstructs fitted XGBoostModel instance from stored JSON."""
        cfg = XGBoostModelConfig.from_dict(self.training_config)
        model = XGBoostModel(config=cfg)
        model.from_json_str(self.model_json, self.feature_names)
        return model

    def get_scaler(self) -> FeatureScaler:
        """Reconstructs fitted FeatureScaler from stored parameters."""
        if self.scaler_state:
            return FeatureScaler.from_dict(self.scaler_state)
        return FeatureScaler(method="none")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MLModelArtifact:
        tp = data["training_period"]
        training_period = (str(tp[0]), str(tp[1])) if tp else ("UNKNOWN", "UNKNOWN")

        vp = data.get("val_period")
        val_period = (str(vp[0]), str(vp[1])) if vp else None

        tep = data.get("test_period")
        test_period = (str(tep[0]), str(tep[1])) if tep else None

        return cls(
            model_json=str(data["model_json"]),
            feature_names=list(data["feature_names"]),
            feature_order=list(data["feature_order"]),
            feature_schema_hash=str(data["feature_schema_hash"]),
            training_config=dict(data.get("training_config", {})),
            label_config=dict(data.get("label_config", {})),
            dataset_metadata=dict(data.get("dataset_metadata", {})),
            training_period=training_period,
            val_period=val_period,
            test_period=test_period,
            random_seed=int(data.get("random_seed", 42)),
            model_version=str(data.get("model_version", "v1.0.0")),
            scaler_state=data.get("scaler_state"),
            feature_importance=dict(data.get("feature_importance", {})),
            classification_metrics=dict(data.get("classification_metrics", {})),
            created_at=str(data.get("created_at", "")),
        )

    def save(self, filepath: str) -> None:
        """Saves artifact to a JSON file."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: str) -> MLModelArtifact:
        """Loads artifact from a JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
