"""API endpoints for Supervised Machine Learning research pipeline (Phase 9 & 11)."""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.app.ml.features import FEATURE_METADATA, FeatureConfig
from backend.app.ml.labels import LabelConfig
from backend.app.ml.model import XGBoostModelConfig
from backend.app.ml.train import train_ml_pipeline, WalkForwardMLEngine
from backend.app.research.dataset import DatasetManager

router = APIRouter(prefix="/ml", tags=["Machine Learning"])
manager = DatasetManager()


class MLTrainRequest(BaseModel):
    dataset_id: str = Field(default="AAPL", description="Dataset identifier or symbol")
    horizon: int = Field(default=5, ge=1, le=100, description="Forward return horizon bars")
    threshold: float = Field(default=0.0, description="Binary classification return threshold")
    n_estimators: int = Field(default=100, ge=10, le=1000)
    max_depth: int = Field(default=4, ge=1, le=10)
    learning_rate: float = Field(default=0.05, gt=0.0, le=1.0)
    seed: int = Field(default=42)
    train_pct: float = Field(default=0.60, gt=0.1, lt=0.9)
    val_pct: float = Field(default=0.20, ge=0.0, lt=0.5)
    test_pct: float = Field(default=0.20, gt=0.05, lt=0.5)
    calibration_method: str = Field(default="none", description="Calibration: 'none', 'sigmoid', 'isotonic'")


class MLWalkForwardRequest(BaseModel):
    dataset_id: str = Field(default="AAPL", description="Dataset identifier or symbol")
    train_bars: int = Field(default=100, ge=30)
    test_bars: int = Field(default=30, ge=10)
    step_bars: int = Field(default=30, ge=5)
    horizon: int = Field(default=5, ge=1, le=50)
    threshold: float = Field(default=0.0)
    n_estimators: int = Field(default=50, ge=10, le=500)
    max_depth: int = Field(default=3, ge=1, le=8)
    learning_rate: float = Field(default=0.05, gt=0.0, le=1.0)
    seed: int = Field(default=42)


@router.get("/features", response_model=Dict[str, Any])
def get_feature_metadata() -> Dict[str, Any]:
    """Returns documentation and mathematical formulas for all available ML features."""
    return FEATURE_METADATA


@router.post("/train", response_model=Dict[str, Any])
def train_model(req: MLTrainRequest) -> Dict[str, Any]:
    """Trains a supervised XGBoost classification pipeline chronologically on specified dataset."""
    try:
        df = manager.load_dataset(req.dataset_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{req.dataset_id}' not found.",
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if len(df) < 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dataset '{req.dataset_id}' has insufficient bars ({len(df)}) for ML training.",
        )

    lbl_cfg = LabelConfig(horizon=req.horizon, threshold=req.threshold)
    mdl_cfg = XGBoostModelConfig(
        n_estimators=req.n_estimators,
        max_depth=req.max_depth,
        learning_rate=req.learning_rate,
        random_seed=req.seed,
    )

    try:
        result = train_ml_pipeline(
            df=df,
            label_config=lbl_cfg,
            model_config=mdl_cfg,
            train_pct=req.train_pct,
            val_pct=req.val_pct,
            test_pct=req.test_pct,
            calibration_method=req.calibration_method,
            symbol=req.dataset_id,
        )
        return result.to_dict()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ML training failed: {str(e)}",
        )


@router.post("/walk-forward", response_model=Dict[str, Any])
def run_ml_walk_forward(req: MLWalkForwardRequest) -> Dict[str, Any]:
    """Executes time-series rolling walk-forward ML evaluation across out-of-sample windows."""
    try:
        df = manager.load_dataset(req.dataset_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{req.dataset_id}' not found.",
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    min_required = req.train_bars + req.test_bars
    if len(df) < min_required:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dataset has {len(df)} bars, but at least {min_required} required for walk-forward.",
        )

    engine = WalkForwardMLEngine(
        symbol=req.dataset_id,
        label_config=LabelConfig(horizon=req.horizon, threshold=req.threshold),
        model_config=XGBoostModelConfig(
            n_estimators=req.n_estimators,
            max_depth=req.max_depth,
            learning_rate=req.learning_rate,
            random_seed=req.seed,
        ),
    )

    try:
        wf_result = engine.run(
            df=df,
            train_bars=req.train_bars,
            test_bars=req.test_bars,
            step_bars=req.step_bars,
        )
        return wf_result.to_dict()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Walk-forward ML failed: {str(e)}",
        )
