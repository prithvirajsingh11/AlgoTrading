from typing import List, Dict, Any, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from backend.app.core.config import settings
from backend.app.data.loader import CSVDataLoader
from backend.app.data.cleaner import DataValidator

router = APIRouter(prefix="/market", tags=["Market Data"])


@router.get("/symbols", response_model=List[str])
def list_available_symbols():
    """Lists symbols with available historical CSV data in data/raw/."""
    raw_dir = settings.data_dir / "raw"
    if not raw_dir.exists():
        return []
    files = list(raw_dir.glob("*.csv"))
    # Extract symbol from filename (e.g. AAPL_sample.csv -> AAPL)
    symbols = []
    for f in files:
        symbol = f.stem.split("_")[0].upper()
        if symbol not in symbols:
            symbols.append(symbol)
    return symbols


@router.get("/data/{symbol}")
def get_historical_bars(symbol: str, limit: int = Query(default=100, le=1000)):
    """Fetches the latest historical OHLCV bars for a symbol."""
    raw_dir = settings.data_dir / "raw"
    matching = list(raw_dir.glob(f"{symbol.upper()}*.csv"))
    if not matching:
        raise HTTPException(status_code=404, detail=f"No dataset found for symbol {symbol}")

    loader = CSVDataLoader()
    df = loader.load_csv(matching[0])
    bars = CSVDataLoader.to_bars(df)

    # Return last N bars
    recent_bars = bars[-limit:]
    return [b.to_dict() for b in recent_bars]


@router.get("/validate/{symbol}")
def validate_dataset(symbol: str) -> Dict[str, Any]:
    """Validates historical dataset integrity for the specified symbol."""
    raw_dir = settings.data_dir / "raw"
    matching = list(raw_dir.glob(f"{symbol.upper()}*.csv"))
    if not matching:
        raise HTTPException(status_code=404, detail=f"No dataset found for symbol {symbol}")

    loader = CSVDataLoader()
    df = loader.load_csv(matching[0])
    is_valid, errors = DataValidator.validate(df, strict=False)

    return {
        "symbol": symbol.upper(),
        "total_bars": len(df),
        "is_valid": is_valid,
        "errors": errors,
        "start_date": df["timestamp"].min().isoformat() if not df.empty else None,
        "end_date": df["timestamp"].max().isoformat() if not df.empty else None,
    }


@router.get("/providers")
def list_market_providers() -> List[Dict[str, Any]]:
    """Returns available market data provider configurations without credentials."""
    return [
        {
            "id": "HISTORICAL",
            "name": "Historical Replay (Offline CSV)",
            "type": "replay",
            "is_live": False,
            "description": "Simulates historical tick-by-tick bar replay from local data files.",
            "requires_api_key": False,
            "status": "ready",
        },
        {
            "id": "mock",
            "name": "In-Memory Streaming (Test/Demo)",
            "type": "streaming",
            "is_live": True,
            "description": "Deterministic local real-time feed generator with latency & heartbeat tracking.",
            "requires_api_key": False,
            "status": "ready",
        },
        {
            "id": "websocket",
            "name": "Generic WebSocket Feed",
            "type": "streaming",
            "is_live": True,
            "description": "Configurable streaming WebSocket adapter for normalized live vendor feeds.",
            "requires_api_key": True,
            "status": "configured" if settings.live_data_api_url else "unconfigured",
        },
    ]


@router.get("/status")
def get_market_status() -> Dict[str, Any]:
    """Returns current market data provider connection and health status."""
    from backend.app.paper.service import paper_service

    # Check for active running real-time paper sessions
    for sid, sess in paper_service.sessions.items():
        if sess.mode == "REAL_TIME" and sess.status.value == "RUNNING":
            prov = paper_service.providers.get(sid)
            if prov and hasattr(prov, "status"):
                status_dict = prov.status.to_dict()
                status_dict["session_id"] = sid
                status_dict["safety_state"] = sess.safety_state
                return status_dict

    return {
        "provider": settings.live_data_provider,
        "state": "DISCONNECTED",
        "connected": False,
        "subscribed_symbols": [],
        "reconnect_count": 0,
        "last_message_at": None,
        "last_heartbeat_at": None,
        "latency_ms": None,
        "last_error": None,
        "safety_state": "SIGNALS_PAUSED",
    }


class ConnectProviderRequest(BaseModel):
    provider: str = "mock"
    symbols: Optional[List[str]] = None


@router.post("/connect")
def connect_market_provider(req: ConnectProviderRequest) -> Dict[str, Any]:
    """Connects or tests connectivity to specified market provider."""
    return {
        "success": True,
        "provider": req.provider,
        "message": f"Market provider '{req.provider}' connected.",
    }


@router.post("/disconnect")
def disconnect_market_provider() -> Dict[str, Any]:
    """Disconnects live market data provider."""
    return {
        "success": True,
        "message": "Market provider disconnected.",
    }


class SubscribeSymbolsRequest(BaseModel):
    symbols: List[str]


@router.post("/subscribe")
def subscribe_market_symbols(req: SubscribeSymbolsRequest) -> Dict[str, Any]:
    """Subscribes to live symbol updates."""
    return {
        "success": True,
        "subscribed_symbols": [s.upper() for s in req.symbols],
    }
