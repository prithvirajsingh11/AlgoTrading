"""Model probability calibration and probability quality assessment.

Provides Platt scaling (sigmoid) and isotonic regression to calibrate raw model
probabilities against empirical frequencies. Gracefully falls back when sample
counts are insufficient.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss


@dataclass
class CalibrationReport:
    """Diagnostic report on probability calibration quality."""

    method: str
    samples_used: int
    brier_before: Optional[float]
    brier_after: Optional[float]
    calibrated: bool
    warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "samples_used": self.samples_used,
            "brier_before": self.brier_before,
            "brier_after": self.brier_after,
            "calibrated": self.calibrated,
            "warning": self.warning,
        }


class ProbabilityCalibrator:
    """Calibrates 1D positive-class probabilities P(class=1)."""

    def __init__(self, method: str = "none", min_samples: int = 50):
        self.method = method.lower()
        self.min_samples = min_samples
        self._sigmoid_model: Optional[LogisticRegression] = None
        self._isotonic_model: Optional[IsotonicRegression] = None
        self.report: Optional[CalibrationReport] = None

    def fit(self, probs: np.ndarray, y_true: np.ndarray) -> ProbabilityCalibrator:
        """Fits calibration curve on validation set probabilities and true labels."""
        p_pos = np.asarray(probs, dtype=float).flatten()
        y = np.asarray(y_true, dtype=int).flatten()

        n = len(p_pos)
        unique_classes = len(np.unique(y))

        # Check conditions
        if self.method in ("none", ""):
            brier = float(brier_score_loss(y, p_pos)) if unique_classes > 0 else None
            self.report = CalibrationReport(
                method="none",
                samples_used=n,
                brier_before=brier,
                brier_after=brier,
                calibrated=False,
                warning=None,
            )
            return self

        if n < self.min_samples or unique_classes < 2:
            brier = float(brier_score_loss(y, p_pos)) if unique_classes > 0 else None
            self.report = CalibrationReport(
                method=self.method,
                samples_used=n,
                brier_before=brier,
                brier_after=brier,
                calibrated=False,
                warning=f"Sample count ({n}) or class diversity ({unique_classes}) below threshold ({self.min_samples}); skipped calibration.",
            )
            return self

        brier_before = float(brier_score_loss(y, p_pos))

        if self.method == "sigmoid":
            # Platt scaling: LogisticRegression on logit(p) or raw p
            # Reshape for sklearn
            X_p = p_pos.reshape(-1, 1)
            clf = LogisticRegression(C=1.0, solver="lbfgs")
            clf.fit(X_p, y)
            self._sigmoid_model = clf
            cal_p = clf.predict_proba(X_p)[:, 1]
            brier_after = float(brier_score_loss(y, cal_p))

            self.report = CalibrationReport(
                method="sigmoid",
                samples_used=n,
                brier_before=round(brier_before, 4),
                brier_after=round(brier_after, 4),
                calibrated=True,
            )

        elif self.method == "isotonic":
            # Non-parametric isotonic regression
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(p_pos, y)
            self._isotonic_model = iso
            cal_p = iso.predict(p_pos)
            brier_after = float(brier_score_loss(y, cal_p))

            self.report = CalibrationReport(
                method="isotonic",
                samples_used=n,
                brier_before=round(brier_before, 4),
                brier_after=round(brier_after, 4),
                calibrated=True,
            )
        else:
            raise ValueError(f"Unknown calibration method: '{self.method}'. Supported: 'none', 'sigmoid', 'isotonic'.")

        return self

    def calibrate(self, probs: np.ndarray) -> np.ndarray:
        """Transforms uncalibrated probabilities to calibrated probabilities."""
        p_pos = np.asarray(probs, dtype=float).flatten()

        if self._sigmoid_model is not None:
            X_p = p_pos.reshape(-1, 1)
            cal_p = self._sigmoid_model.predict_proba(X_p)[:, 1]
            return np.clip(cal_p, 0.0, 1.0)

        if self._isotonic_model is not None:
            cal_p = self._isotonic_model.predict(p_pos)
            return np.clip(cal_p, 0.0, 1.0)

        return p_pos

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "min_samples": self.min_samples,
            "report": self.report.to_dict() if self.report else None,
        }
