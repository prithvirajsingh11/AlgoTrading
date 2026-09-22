"""Deterministic generator for standard benchmark datasets in data/demo.

Generates reproducible geometric Brownian motion OHLCV data with:
- Fixed random seeds for 100% reproducibility
- Realistic daily/minute price paths, realistic volatility, and volume
- Both single-asset (benchmark_single_asset.csv) and synchronized multi-asset (benchmark_multi_asset.csv)
- 100% offline, local, safe to commit to GitHub
"""

from __future__ import annotations
import math
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd


def generate_gbm_ohlcv(
    symbol: str,
    start_price: float,
    start_date: datetime,
    num_bars: int = 5000,
    mu: float = 0.0003,       # ~7.5% annual drift
    sigma: float = 0.015,     # ~24% annual volatility
    dt_minutes: int = 60,     # Hourly or customizable interval
    seed: int = 42,
) -> pd.DataFrame:
    """Generates synthetic OHLCV bars using a seeded Geometric Brownian Motion model."""
    rng = np.random.default_rng(seed)
    
    # Generate log returns
    dt = 1.0
    returns = rng.normal(loc=(mu - 0.5 * sigma**2) * dt, scale=sigma * math.sqrt(dt), size=num_bars)
    
    # Compute close prices
    log_prices = np.log(start_price) + np.cumsum(returns)
    closes = np.exp(log_prices)
    
    timestamps: List[datetime] = []
    opens: List[float] = []
    highs: List[float] = []
    lows: List[float] = []
    final_closes: List[float] = []
    volumes: List[float] = []
    
    cur_time = start_date
    prev_close = start_price
    
    for i in range(num_bars):
        c = float(closes[i])
        # Open is near previous close
        o = float(prev_close * (1.0 + rng.normal(0, 0.0015)))
        # High and Low envelope
        intraday_vol = abs(c - o) + (c * rng.uniform(0.002, 0.008))
        h = float(max(o, c) + intraday_vol * rng.uniform(0.3, 0.8))
        l = float(min(o, c) - intraday_vol * rng.uniform(0.3, 0.8))
        # Ensure positive
        l = max(0.01, l)
        h = max(h, max(o, c))
        # Volume
        base_vol = 50_000
        vol = float(int(base_vol * rng.lognormal(mean=0.0, sigma=0.5)))
        
        timestamps.append(cur_time)
        opens.append(round(o, 2))
        highs.append(round(h, 2))
        lows.append(round(l, 2))
        final_closes.append(round(c, 2))
        volumes.append(vol)
        
        prev_close = c
        cur_time += timedelta(minutes=dt_minutes)
        
    df = pd.DataFrame({
        "timestamp": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": final_closes,
        "volume": volumes,
        "symbol": symbol,
    })
    return df


def generate_benchmark_datasets(output_dir: Path | str | None = None) -> Dict[str, Path]:
    """Generates standard benchmark datasets in data/demo/."""
    if output_dir is None:
        target_dir = Path(__file__).resolve().parent.parent.parent.parent / "data" / "demo"
    else:
        target_dir = Path(output_dir)
        
    target_dir.mkdir(parents=True, exist_ok=True)
    start_dt = datetime(2023, 1, 3, 9, 30, tzinfo=timezone.utc)
    
    # 1. Single asset benchmark (5,000 bars)
    df_single = generate_gbm_ohlcv(
        symbol="AAPL",
        start_price=150.0,
        start_date=start_dt,
        num_bars=5000,
        seed=101,
    )
    single_path = target_dir / "benchmark_single_asset.csv"
    # Export without symbol column for single-asset standard compatibility
    df_single[["timestamp", "open", "high", "low", "close", "volume"]].to_csv(single_path, index=False)
    
    # 2. Multi-asset benchmark (2,500 bars each for AAPL, MSFT, SPY synchronized)
    df_aapl = generate_gbm_ohlcv(symbol="AAPL", start_price=150.0, start_date=start_dt, num_bars=2500, seed=201)
    df_msft = generate_gbm_ohlcv(symbol="MSFT", start_price=240.0, start_date=start_dt, num_bars=2500, seed=202)
    df_spy = generate_gbm_ohlcv(symbol="SPY", start_price=385.0, start_date=start_dt, num_bars=2500, seed=203)
    
    df_multi = pd.concat([df_aapl, df_msft, df_spy], ignore_index=True)
    df_multi.sort_values(by=["timestamp", "symbol"], inplace=True)
    multi_path = target_dir / "benchmark_multi_asset.csv"
    df_multi.to_csv(multi_path, index=False)
    
    return {
        "single_asset": single_path,
        "multi_asset": multi_path,
    }


if __name__ == "__main__":
    paths = generate_benchmark_datasets()
    print(f"Generated benchmark datasets:\n  Single: {paths['single_asset']}\n  Multi:  {paths['multi_asset']}")
