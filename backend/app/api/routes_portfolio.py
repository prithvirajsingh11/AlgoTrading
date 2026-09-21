from typing import Dict, Any, List
from fastapi import APIRouter
from backend.app.core.config import settings

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])


@router.get("/summary")
def get_portfolio_summary() -> Dict[str, Any]:
    """Returns general portfolio status summary (stub for paper trading / live simulation)."""
    return {
        "account_id": "paper_demo_account",
        "currency": "USD",
        "initial_capital": settings.default_initial_capital,
        "current_cash": settings.default_initial_capital,
        "positions_count": 0,
        "status": "PAPER_TRADING_STANDBY",
    }


@router.get("/positions", response_model=List[Dict[str, Any]])
def list_positions():
    """Lists current open positions in paper trading account."""
    return []
