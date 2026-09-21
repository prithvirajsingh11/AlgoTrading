import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, Request, Response, WebSocket, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import settings
from backend.app.core.logging import setup_logging
from backend.app.core.middleware import RequestCorrelationMiddleware

from backend.app.api.routes_market import router as market_router
from backend.app.api.routes_strategy import router as strategy_router
from backend.app.api.routes_backtest import router as backtest_router
from backend.app.api.routes_portfolio import router as portfolio_router
from backend.app.api.routes_paper import router as paper_router, paper_ws_handler
from backend.app.api.routes_datasets import router as datasets_router
from backend.app.api.routes_experiments import router as experiments_router
from backend.app.api.routes_ai import router as ai_router
from backend.app.api.routes_ml import router as ml_router

# Initialize structured logging
setup_logging(settings.log_level)
logger = logging.getLogger("algotrade")

app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    description="Realistic algorithmic trading research, backtesting, and paper-trading engine.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS setup
cors_origins = [o.strip() for o in settings.cors_origins.split(",")] if "," in settings.cors_origins else [settings.cors_origins]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request tracking and correlation middleware
app.add_middleware(RequestCorrelationMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catches unhandled exceptions, logs full context, and returns sanitized error to client."""
    req_id = getattr(request.state, "request_id", "unknown")
    logger.exception(
        f"Internal server error processing {request.method} {request.url.path}: {exc}",
        extra={"request_id": req_id, "component": "app", "event": "internal_error"},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred while processing the request.",
            "request_id": req_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        headers={"X-Request-ID": req_id},
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
app.include_router(ai_router, prefix=api_v1_prefix)
app.include_router(ml_router, prefix=api_v1_prefix)


@app.websocket("/ws/paper/{session_id}")
async def direct_paper_ws(websocket: WebSocket, session_id: str):
    await paper_ws_handler(websocket, session_id)


@app.get("/health", tags=["Health"])
def health_check():
    """Liveness probe indicating whether the API process is alive."""
    return {
        "status": "healthy",
        "service": "algotrade-backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project": settings.project_name,
        "environment": settings.environment,
        "mode": "paper_and_backtest_only",
    }


@app.get("/ready", tags=["Health"])
def readiness_check(response: Response):
    """Readiness probe checking storage writability, raw data availability, and dependencies."""
    raw_dir = settings.data_dir / "raw"
    checks = {
        "storage": True,
        "datasets": True,
        "raw_data_dir": bool(raw_dir.exists()),
        "paper_storage": True,
        "jev_configured": settings.jev_enabled,
    }
    reasons = []

    # 1. Check data directory exists and is writable
    try:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        test_file = settings.data_dir / ".readiness_probe"
        test_file.write_text("probe", encoding="utf-8")
        test_file.unlink(missing_ok=True)
    except Exception as e:
        checks["storage"] = False
        checks["paper_storage"] = False
        reasons.append(f"Storage path not writable: {e}")

    # 2. Check raw datasets directory
    if not raw_dir.exists():
        checks["datasets"] = False
        checks["raw_data_dir"] = False
        reasons.append(f"Raw data directory not found: {raw_dir}")

    is_ready = checks["storage"] and checks["datasets"]
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if is_ready else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "reasons": reasons,
    }


@app.get("/", tags=["Root"])
def root():
    return {
        "message": "Welcome to AlgoTrade API",
        "docs_url": "/docs",
        "version": "0.1.0",
        "trading_mode": "SIMULATION_ONLY",
    }
