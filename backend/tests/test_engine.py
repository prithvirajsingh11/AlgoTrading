import pandas as pd
from pathlib import Path
from backend.app.strategies.momentum import MovingAverageCrossStrategy
from backend.app.backtesting.engine import BacktestEngine
from backend.app.risk.position_sizing import FixedQuantitySizer
from backend.app.data.loader import CSVDataLoader


def test_engine_chronological_integrity():
    """Verifies that engine iterates chronologically and equity records match timestamps."""
    dates = pd.date_range("2023-01-01", periods=30)
    prices = [100.0 + i for i in range(30)]

    df = pd.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": [p + 2.0 for p in prices],
        "low": [p - 2.0 for p in prices],
        "close": prices,
        "volume": [1000] * 30,
    })

    strategy = MovingAverageCrossStrategy(symbol="TEST", fast_period=3, slow_period=6)
    engine = BacktestEngine(
        symbol="TEST",
        initial_capital=50_000.0,
        position_sizer=FixedQuantitySizer(quantity=10.0),
    )

    result = engine.run(df=df, strategy=strategy)

    # Verifying chronology of equity points
    equity_curve = result.equity_curve
    assert len(equity_curve) == 30
    timestamps = [pt["timestamp"] for pt in equity_curve]
    assert timestamps == sorted(timestamps)

    # Initial equity should match
    assert result.metrics.initial_capital == 50_000.0
    assert result.strategy_name == "MovingAverageCross"


def test_engine_on_sample_csv():
    csv_path = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "AAPL_sample.csv"
    assert csv_path.exists(), f"Sample CSV file missing at {csv_path}"

    loader = CSVDataLoader()
    df = loader.load_csv(csv_path)

    strategy = MovingAverageCrossStrategy(symbol="AAPL", fast_period=10, slow_period=30)
    engine = BacktestEngine(
        symbol="AAPL",
        initial_capital=100_000.0,
    )

    result = engine.run(df=df, strategy=strategy)

    assert len(result.equity_curve) == len(df)
    assert result.metrics.initial_capital == 100_000.0
    assert result.metrics.final_equity > 0.0
    assert result.metrics.maximum_drawdown >= 0.0
