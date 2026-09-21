"""Classification performance metrics for supervised machine learning models.

Evaluates accuracy, precision, recall, F1, ROC-AUC, Brier score, and confusion matrix.
Does not rely on accuracy alone.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    brier_score_loss,
    confusion_matrix,
    log_loss,
)


@dataclass
class ClassificationMetrics:
    """Comprehensive classification metrics for ML evaluation."""

    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: Optional[float]
    brier_score: Optional[float]
    log_loss: Optional[float]
    confusion_matrix: List[List[int]]
    positive_count: int
    negative_count: int
    total_samples: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_classification(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: Optional[np.ndarray] = None,
) -> ClassificationMetrics:
    """Computes comprehensive classification metrics.

    Handles single-class edge cases gracefully without raising mathematical errors.
    """
    y_true_arr = np.asarray(y_true, dtype=int)
    y_pred_arr = np.asarray(y_pred, dtype=int)

    total_samples = int(len(y_true_arr))
    if total_samples == 0:
        return ClassificationMetrics(
            accuracy=0.0,
            precision=0.0,
            recall=0.0,
            f1=0.0,
            roc_auc=None,
            brier_score=None,
            log_loss=None,
            confusion_matrix=[[0, 0], [0, 0]],
            positive_count=0,
            negative_count=0,
            total_samples=0,
        )

    pos_count = int(np.sum(y_true_arr == 1))
    neg_count = int(np.sum(y_true_arr == 0))

    acc = float(accuracy_score(y_true_arr, y_pred_arr))
    prec = float(precision_score(y_true_arr, y_pred_arr, zero_division=0))
    rec = float(recall_score(y_true_arr, y_pred_arr, zero_division=0))
    f1 = float(f1_score(y_true_arr, y_pred_arr, zero_division=0))

    # Confusion matrix: [[TN, FP], [FN, TP]]
    cm = confusion_matrix(y_true_arr, y_pred_arr, labels=[0, 1]).tolist()

    # Probabilistic metrics
    roc_auc: Optional[float] = None
    brier: Optional[float] = None
    ll: Optional[float] = None

    if y_prob is not None and len(y_prob) == total_samples:
        prob_arr = np.asarray(y_prob, dtype=float)
        # If shape is (N, 2), extract P(class=1)
        if prob_arr.ndim == 2 and prob_arr.shape[1] == 2:
            p_pos = prob_arr[:, 1]
        else:
            p_pos = prob_arr.flatten()

        # Brier score is always well-defined
        brier = float(brier_score_loss(y_true_arr, p_pos))

        # ROC-AUC and Log-Loss require at least 2 distinct classes in y_true
        if len(np.unique(y_true_arr)) >= 2:
            try:
                roc_auc = float(roc_auc_score(y_true_arr, p_pos))
            except Exception:
                roc_auc = None

            try:
                ll = float(log_loss(y_true_arr, p_pos, labels=[0, 1]))
            except Exception:
                ll = None

    return ClassificationMetrics(
        accuracy=round(acc, 4),
        precision=round(prec, 4),
        recall=round(rec, 4),
        f1=round(f1, 4),
        roc_auc=round(roc_auc, 4) if roc_auc is not None else None,
        brier_score=round(brier, 4) if brier is not None else None,
        log_loss=round(ll, 4) if ll is not None else None,
        confusion_matrix=cm,
        positive_count=pos_count,
        negative_count=neg_count,
        total_samples=total_samples,
    )
