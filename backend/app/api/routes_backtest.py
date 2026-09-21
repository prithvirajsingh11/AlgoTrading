from typing import Dict, Any, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from backend.app.core.config import settings
from backend.app.data.loader import CSVDataLoader
from backend.app.strategies.momentum import MovingAverageCrossStrategy
from backend.app.backtesting.engine import BacktestEngine
from backend.app.backtesting.broker import SimulatedBroker
from backend.app.risk.position_sizing import PercentEquitySizer
from backend.app.risk.risk_manager import RiskManager
from backend.app.risk.metrics import BacktestResult

router = APIRouter(prefix="/backtest", tags=["Backtesting"])


class BacktestRunRequest(BaseModel):
    symbol: str = Field(default="AAPL", description="Asset symbol to backtest")
    strategy: str = Field(default="MovingAverageCross", description="Strategy identifier")
    parameters: Dict[str, Any] = Field(
        default={"fast_period": 10, "slow_period": 30},
        description="Configurable strategy parameters",
    )
    initial_capital: float = Field(default=100_000.0, ge=1000.0)
    commission_fixed: float = Field(default=1.0, ge=0.0)
    commission_percent: float = Field(default=0.0005, ge=0.0)
    slippage_bps: float = Field(default=5.0, ge=0.0)
    position_size_pct: float = Field(default=0.20, gt=0.0, le=1.0)
    max_position_pct: float = Field(default=0.50, gt=0.0, le=1.0)
    max_drawdown_limit: float = Field(default=0.30, gt=0.0, le=1.0)


@router.post("/run", response_model=BacktestResult)
def run_backtest(req: BacktestRunRequest):
    """Executes a chronological event-driven backtest for a strategy over local historical data."""
    raw_dir = settings.data_dir / "raw"
    matching = list(raw_dir.glob(f"{req.symbol.upper()}*.csv"))
    if not matching:
        raise HTTPException(
            status_code=404,
            detail=f"Historical data for symbol '{req.symbol}' not found in {raw_dir}",
        )

    # 1. Load data
    loader = CSVDataLoader()
    try:
        df = loader.load_csv(matching[0])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed loading dataset: {str(e)}")

    # 2. Instantiate strategy
    if req.strategy == "MovingAverageCross":
        try:
            strategy = MovingAverageCrossStrategy(
                symbol=req.symbol.upper(),
                parameters=req.parameters,
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Strategy '{req.strategy}' is not active or supported yet.",
        )

    # 3. Setup risk manager, broker, and position sizer
    broker = SimulatedBroker(
        commission_fixed=req.commission_fixed,
        commission_percent=req.commission_percent,
        slippage_bps=req.slippage_bps,
    )
    risk_manager = RiskManager(
        max_position_pct=req.max_position_pct,
        max_drawdown_limit=req.max_drawdown_limit,
        allow_shorting=False,
    )
    sizer = PercentEquitySizer(percent_equity=req.position_size_pct)

    # 4. Run Backtest
    engine = BacktestEngine(
        symbol=req.symbol.upper(),
        initial_capital=req.initial_capital,
        broker=broker,
        risk_manager=risk_manager,
        position_sizer=sizer,
    )

    try:
        result = engine.run(df=df, strategy=strategy)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backtest execution error: {str(e)}")
