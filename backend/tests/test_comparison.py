from pathlib import Path
import pytest

from backend.app.data.loader import CSVDataLoader
from backend.app.strategies.momentum import MovingAverageCrossStrategy, TimeSeriesMomentumStrategy
from backend.app.strategies.mean_reversion import MeanReversionStrategy
from backend.app.backtesting.comparison import StrategyComparator, StrategyComparisonResult


def test_strategy_comparator_execution():
    csv_path = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "AAPL_sample.csv"
    loader = CSVDataLoader()
    df = loader.load_csv(csv_path)

    strat1 = MovingAverageCrossStrategy(symbol="AAPL", fast_period=10, slow_period=30)
    strat2 = TimeSeriesMomentumStrategy(symbol="AAPL", lookback_period=20, entry_threshold=0.02, exit_threshold=-0.01)
    strat3 = MeanReversionStrategy(symbol="AAPL", lookback_period=20, entry_z_score=-1.5, exit_z_score=0.0)

    comparator = StrategyComparator(initial_capital=100_000.0)
    result: StrategyComparisonResult = comparator.compare(
        df=df,
        strategies=[strat1, strat2, strat3],
        rank_by="sharpe_ratio",
    )

    assert result.symbol == "AAPL"
    assert result.dataset_bars == len(df)
    assert len(result.strategies) == 3
    assert result.ranked_by == "sharpe_ratio"

    # Verify all 9 required metrics are present on each strategy
    for s in result.strategies:
        assert hasattr(s, "total_return")
        assert hasattr(s, "cagr")
        assert hasattr(s, "volatility")
        assert hasattr(s, "sharpe_ratio")
        assert hasattr(s, "sortino_ratio")
        assert hasattr(s, "maximum_drawdown")
        assert hasattr(s, "win_rate")
        assert hasattr(s, "trade_count")
        assert hasattr(s, "profit_factor")

        assert isinstance(s.total_return, float)
        assert isinstance(s.cagr, float)
        assert isinstance(s.volatility, float)
        assert isinstance(s.sharpe_ratio, float)
        assert isinstance(s.sortino_ratio, float)
        assert isinstance(s.maximum_drawdown, float)
        assert isinstance(s.win_rate, float)
        assert isinstance(s.trade_count, int)
        assert isinstance(s.profit_factor, float)

    # Check ranking ordering (descending by Sharpe ratio)
    sharpes = [s.sharpe_ratio for s in result.strategies]
    assert sharpes == sorted(sharpes, reverse=True)

    # Verify equity curves are stored for each strategy
    assert len(result.equity_curves) == 3
    assert "MovingAverageCross" in result.equity_curves
    assert "TimeSeriesMomentum" in result.equity_curves
    assert "MeanReversion" in result.equity_curves


def test_strategy_comparator_empty_error():
    comparator = StrategyComparator()
    with pytest.raises(ValueError, match="at least one strategy"):
        comparator.compare(df=None, strategies=[])
