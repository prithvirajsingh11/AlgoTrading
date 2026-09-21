"""API endpoints for managing and executing reproducible research experiments."""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.research.config import ExperimentConfig
from backend.app.research.runner import ExperimentRunner
from backend.app.research.storage import SQLiteExperimentStorage

router = APIRouter(prefix="/experiments", tags=["Experiments"])
storage = SQLiteExperimentStorage()
runner = ExperimentRunner(storage=storage)


@router.post("", response_model=Dict[str, Any])
def create_and_run_experiment(config_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Creates and immediately executes a reproducible backtest experiment from ExperimentConfig."""
    try:
        config = ExperimentConfig.from_dict(config_payload)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid ExperimentConfig schema: {str(e)}")

    try:
        result = runner.run_experiment(config)
        return result.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Experiment execution failed: {str(e)}")


@router.get("", response_model=List[Dict[str, Any]])
def list_experiments(limit: int = 100) -> List[Dict[str, Any]]:
    """Lists persisted experiments with summary metrics."""
    return storage.list_experiments(limit=limit)


class ExperimentCompareRequest(BaseModel):
    experiment_ids: List[str] = Field(..., description="List of experiment IDs to compare")


@router.post("/compare", response_model=Dict[str, Any])
def compare_experiments(req: ExperimentCompareRequest) -> Dict[str, Any]:
    """Compares multiple experiments across Traditional, ML, and Jev dimensions."""
    if not req.experiment_ids:
        raise HTTPException(status_code=400, detail="experiment_ids cannot be empty.")

    experiments = []
    for exp_id in req.experiment_ids:
        res = storage.load_experiment(exp_id)
        if res is not None:
            experiments.append(res)

    if not experiments:
        raise HTTPException(status_code=404, detail="None of the specified experiments were found.")

    from backend.app.research.runner import compare_strategy_providers
    return compare_strategy_providers(experiments)


@router.get("/{experiment_id}", response_model=Dict[str, Any])
def get_experiment(experiment_id: str) -> Dict[str, Any]:
    """Retrieves full experiment artifacts (equity curves, trades, metrics, configs)."""
    result = storage.load_experiment(experiment_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")
    return result.to_dict()


@router.post("/{experiment_id}/run", response_model=Dict[str, Any])
def rerun_experiment(experiment_id: str) -> Dict[str, Any]:
    """Re-executes an existing experiment using its persisted configuration."""
    saved_result = storage.load_experiment(experiment_id)
    if not saved_result:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found.")

    config = ExperimentConfig.from_dict(saved_result.config)
    try:
        new_result = runner.run_experiment(config)
        return new_result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Re-execution failed: {str(e)}")
