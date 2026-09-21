from typing import Dict, Any
from fastapi import APIRouter

router = APIRouter(prefix="/paper", tags=["Paper Trading"])


@router.get("/status")
def get_paper_trading_status() -> Dict[str, Any]:
    """Paper trading engine status endpoint (stub for live paper simulation phase)."""
    return {
        "is_active": False,
        "mode": "SIMULATION_ONLY",
        "message": "Paper trading daemon reserved for live paper-trading phase.",
    }


@router.post("/start")
def start_paper_trading() -> Dict[str, str]:
    return {"status": "NOT_IMPLEMENTED", "message": "Paper trading daemon reserved for subsequent phase."}


@router.post("/stop")
def stop_paper_trading() -> Dict[str, str]:
    return {"status": "STOPPED", "message": "No active paper trading daemon running."}
