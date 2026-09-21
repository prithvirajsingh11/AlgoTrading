from typing import List, Dict, Any
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
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
