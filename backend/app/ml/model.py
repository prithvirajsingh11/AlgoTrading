"""XGBoost classification model wrapper with deterministic training and feature importance.

Ensures strict reproducibility via seed control and exposes structured feature importance
without leaking future data.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
import pandas as pd
import xgboost as xgb


@dataclass
class XGBoostModelConfig:
    """Configurable hyperparameters for baseline XGBoost classifier."""

    n_estimators: int = 100
    learning_rate: float = 0.05
    max_depth: int = 4
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    min_child_weight: float = 1.0
    reg_alpha: float = 0.0
    reg_lambda: float = 1.0
    random_seed: int = 42
    early_stopping_rounds: Optional[int] = 10
    eval_metric: str = "logloss"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> XGBoostModelConfig:
        return cls(
            n_estimators=int(data.get("n_estimators", 100)),
            learning_rate=float(data.get("learning_rate", 0.05)),
            max_depth=int(data.get("max_depth", 4)),
            subsample=float(data.get("subsample", 0.8)),
            colsample_bytree=float(data.get("colsample_bytree", 0.8)),
            min_child_weight=float(data.get("min_child_weight", 1.0)),
            reg_alpha=float(data.get("reg_alpha", 0.0)),
            reg_lambda=float(data.get("reg_lambda", 1.0)),
            random_seed=int(data.get("random_seed", 42)),
            early_stopping_rounds=int(data["early_stopping_rounds"]) if data.get("early_stopping_rounds") is not None else None,
            eval_metric=str(data.get("eval_metric", "logloss")),
        )


class XGBoostModel:
    """Production-grade XGBoost classification model."""

    def __init__(self, config: Optional[XGBoostModelConfig] = None):
        self.config = config or XGBoostModelConfig()
        self.feature_names: List[str] = []
        self._classifier: Optional[xgb.XGBClassifier] = None
        self._booster: Optional[xgb.Booster] = None

    @property
    def booster(self) -> Optional[xgb.Booster]:
        if self._booster is not None:
            return self._booster
        if self._classifier is not None:
            try:
                return self._classifier.get_booster()
            except Exception:
                return None
        return None

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ) -> XGBoostModel:
        """Fits XGBoost classifier with deterministic random seed."""
        self.feature_names = list(X_train.columns)

        has_val = (
            X_val is not None
            and y_val is not None
            and not X_val.empty
            and len(np.unique(y_val)) > 1
        )

        early_rounds = self.config.early_stopping_rounds if has_val else None

        self._classifier = xgb.XGBClassifier(
            n_estimators=self.config.n_estimators,
            learning_rate=self.config.learning_rate,
            max_depth=self.config.max_depth,
            subsample=self.config.subsample,
            colsample_bytree=self.config.colsample_bytree,
            min_child_weight=self.config.min_child_weight,
            reg_alpha=self.config.reg_alpha,
            reg_lambda=self.config.reg_lambda,
            random_state=self.config.random_seed,
            eval_metric=self.config.eval_metric,
            early_stopping_rounds=early_rounds,
            n_jobs=1,  # Single-threaded for bit-level determinism across platforms
        )

        if has_val:
            self._classifier.fit(
                X_train,
                y_train,
                eval_set=[(X_val, y_val)],
                verbose=False,
            )
        else:
            self._classifier.fit(
                X_train,
                y_train,
                verbose=False,
            )

        self._booster = self._classifier.get_booster()
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Returns predicted probability distribution shape (N, 2) -> [P(class=0), P(class=1)]."""
        b = self.booster
        if b is None:
            raise RuntimeError("Model must be fitted before predict_proba can be called.")
        X_ordered = X[self.feature_names]
        dmat = xgb.DMatrix(X_ordered)
        preds = b.predict(dmat)
        if preds.ndim == 1:
            p_pos = preds
            p_neg = 1.0 - p_pos
            return np.column_stack([p_neg, p_pos])
        elif preds.ndim == 2 and preds.shape[1] == 2:
            return preds
        return preds

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Returns discrete 0/1 class predictions."""
        probs = self.predict_proba(X)
        return (probs[:, 1] >= 0.5).astype(int)

    def get_feature_importance(self, importance_type: str = "gain") -> Dict[str, float]:
        """Extracts normalized feature importance mapping."""
        b = self.booster
        if b is None:
            raise RuntimeError("Model must be fitted before extracting feature importance.")

        score_dict = b.get_score(importance_type=importance_type)

        total = sum(score_dict.values()) if score_dict else 0.0
        importances: Dict[str, float] = {}

        for i, name in enumerate(self.feature_names):
            val = score_dict.get(name, score_dict.get(f"f{i}", 0.0))
            norm_val = (val / total) if total > 0 else 0.0
            importances[name] = round(float(norm_val), 6)

        return importances

    def to_json_str(self) -> str:
        """Serializes booster model to raw JSON string."""
        b = self.booster
        if b is None:
            raise RuntimeError("Cannot serialize unfitted model.")
        try:
            raw_bytes = b.save_raw(raw_format="json")
        except TypeError:
            raw_bytes = b.save_raw()
        return raw_bytes.decode("utf-8", errors="replace")

    def from_json_str(self, json_str: str, feature_names: List[str]) -> XGBoostModel:
        """Reconstructs fitted model from JSON string."""
        self.feature_names = list(feature_names)
        booster = xgb.Booster()
        booster.load_model(bytearray(json_str.encode("utf-8")))
        self._booster = booster
        return self
