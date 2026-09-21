"""API endpoints for dataset discovery, metadata inspection, and validation."""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
from backend.app.research.dataset import DatasetManager
from backend.app.research.validator import DatasetValidator

router = APIRouter(prefix="/datasets", tags=["Datasets"])
manager = DatasetManager()


@router.get("", response_model=List[Dict[str, Any]])
def list_datasets() -> List[Dict[str, Any]]:
    """Lists all discovered datasets and their metadata."""
    datasets = manager.discover_datasets()
    return [d.to_dict() for d in datasets]


@router.get("/{dataset_id}", response_model=Dict[str, Any])
def get_dataset(dataset_id: str) -> Dict[str, Any]:
    """Retrieves metadata for a specific dataset ID."""
    meta = manager.get_dataset_metadata(dataset_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found.")
    return meta.to_dict()


@router.post("/{dataset_id}/validate", response_model=Dict[str, Any])
def validate_dataset(dataset_id: str) -> Dict[str, Any]:
    """Runs a non-throwing quantitative integrity validation on the specified dataset."""
    try:
        df = manager.load_dataset(dataset_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed loading dataset '{dataset_id}': {str(e)}")

    report = DatasetValidator.validate(df)
    return report.to_dict()
