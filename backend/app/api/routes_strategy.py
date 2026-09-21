from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/strategies", tags=["Strategies"])

AVAILABLE_STRATEGIES = [
    {
        "id": "MovingAverageCross",
        "name": "Moving Average Crossover",
        "category": "Momentum",
        "description": "Trend-following strategy that generates BUY signals on golden cross and SELL signals on death cross.",
        "status": "ACTIVE",
        "parameters": [
            {
                "name": "fast_period",
                "type": "int",
                "default": 10,
                "description": "Lookback window for the short-term simple moving average.",
            },
            {
                "name": "slow_period",
                "type": "int",
                "default": 30,
                "description": "Lookback window for the long-term simple moving average.",
            },
        ],
    },
    {
        "id": "TimeSeriesMomentum",
        "name": "Time-Series Return Momentum",
        "category": "Momentum",
        "description": "Generates BUY signals when historical returns exceed threshold, exits on drops.",
        "status": "ACTIVE",
        "parameters": [
            {"name": "lookback_period", "type": "int", "default": 20},
            {"name": "entry_threshold", "type": "float", "default": 0.02},
            {"name": "exit_threshold", "type": "float", "default": -0.01},
        ],
    },
    {
        "id": "MeanReversion",
        "name": "Statistical Mean Reversion (Z-Score)",
        "category": "Mean Reversion",
        "description": "Buys when asset price drops below rolling z-score entry threshold and exits on mean reversion.",
        "status": "ACTIVE",
        "parameters": [
            {"name": "lookback_period", "type": "int", "default": 20},
            {"name": "entry_z_score", "type": "float", "default": -2.0},
            {"name": "exit_z_score", "type": "float", "default": 0.0},
        ],
    },
    {
        "id": "PairsTrading",
        "name": "Statistical Arbitrage Pairs Trading",
        "category": "Arbitrage",
        "description": "Trades cointegrated spread reversion between two assets.",
        "status": "ACTIVE",
        "parameters": [
            {"name": "hedge_symbol", "type": "str", "default": "HEDGE"},
            {"name": "lookback_period", "type": "int", "default": 30},
            {"name": "entry_threshold", "type": "float", "default": 2.0},
            {"name": "exit_threshold", "type": "float", "default": 0.5},
        ],
    },
    {
        "id": "MLTradingStrategy",
        "name": "XGBoost Machine Learning Classifier",
        "category": "Machine Learning",
        "description": "Predicts next-bar return sign using gradient boosted trees.",
        "status": "COMING_SOON",
        "parameters": [
            {"name": "confidence_threshold", "type": "float", "default": 0.60},
        ],
    },
]


@router.get("", response_model=List[Dict[str, Any]])
def list_strategies():
    """Lists all available trading strategies and their parameter schemas."""
    return AVAILABLE_STRATEGIES


@router.get("/{strategy_id}")
def get_strategy_details(strategy_id: str):
    """Retrieves strategy configuration metadata."""
    for s in AVAILABLE_STRATEGIES:
        if s["id"].lower() == strategy_id.lower():
            return s
    raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found.")
