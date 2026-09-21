import logging
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.api.routes_market import router as market_router
from backend.app.api.routes_strategy import router as strategy_router
from backend.app.api.routes_backtest import router as backtest_router
from backend.app.api.routes_portfolio import router as portfolio_router
from backend.app.api.routes_paper import router as paper_router
from backend.app.api.routes_datasets import router as datasets_router
from backend.app.api.routes_experiments import router as experiments_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("algotrade")

app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    description="Realistic algorithmic trading research, backtesting, and paper-trading engine.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API v1 Routers
api_v1_prefix = settings.api_v1_str
app.include_router(market_router, prefix=api_v1_prefix)
app.include_router(strategy_router, prefix=api_v1_prefix)
app.include_router(backtest_router, prefix=api_v1_prefix)
app.include_router(portfolio_router, prefix=api_v1_prefix)
app.include_router(paper_router, prefix=api_v1_prefix)
app.include_router(datasets_router, prefix=api_v1_prefix)
app.include_router(experiments_router, prefix=api_v1_prefix)


@app.get("/health", tags=["Health"])
def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project": settings.project_name,
        "environment": settings.environment,
        "mode": "paper_and_backtest_only",
    }


@app.get("/", tags=["Root"])
def root():
    return {
        "message": "Welcome to AlgoTrade API",
        "docs_url": "/docs",
        "version": "0.1.0",
        "trading_mode": "SIMULATION_ONLY",
    }
