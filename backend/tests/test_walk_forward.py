import pytest
import pandas as pd
from pathlib import Path

from backend.app.data.loader import CSVDataLoader
from backend.app.strategies.momentum import MovingAverageCrossStrategy, TimeSeriesMomentumStrategy
from backend.app.backtesting.walk_forward import WalkForwardEngine, WalkForwardResult


def test_walk_forward_window_slices():
    # 100 bars, train=40, test=20, step=20
    # Window 0: Train [0..40], Test [40..60]
    # Window 1: Train [20..60], Test [60..80]
    # Window 2: Train [40..80], Test [80..100]
    slices = WalkForwardEngine.generate_window_slices(
        total_bars=100,
        train_bars=40,
        test_bars=20,
        step_bars=20,
    )
    assert len(slices) == 3
    assert slices[0] == (0, 40, 40, 60)
    assert slices[1] == (20, 60, 60, 80)
    assert slices[2] == (40, 80, 80, 100)

    # Verification: test starts strictly at train_end (no lookahead, chronological)
    for tr_s, tr_e, te_s, te_e in slices:
        assert tr_s < tr_e
        assert tr_e == te_s
        assert te_s < te_e


def test_walk_forward_validation_errors():
    with pytest.raises(ValueError, match="exceed total bars"):
        WalkForwardEngine.generate_window_slices(
            total_bars=50,
            train_bars=40,
            test_bars=20,
            step_bars=10,
        )

    with pytest.raises(ValueError, match="positive integers"):
        WalkForwardEngine.generate_window_slices(100, -10, 20, 10)


def test_walk_forward_execution_on_sample_data():
    csv_path = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "AAPL_sample.csv"
    loader = CSVDataLoader()
    df = loader.load_csv(csv_path)

    engine = WalkForwardEngine(
        symbol="AAPL",
        initial_capital=100_000.0,
    )

    # df has 259 bars. Use train=60, test=30, step=30
    result: WalkForwardResult = engine.run(
        df=df,
        strategy_class=MovingAverageCrossStrategy,
        strategy_params={"fast_period": 5, "slow_period": 15},
        train_bars=60,
        test_bars=30,
        step_bars=30,
    )

    assert result.total_windows >= 5
    assert len(result.windows) == result.total_windows

    # Verify each window has out-of-sample metrics
    for w in result.windows:
        assert w.train_bars == 60
        assert w.test_bars == 30
        assert w.metrics.initial_capital == 100_000.0
        assert len(w.equity_curve) == 30
        # Check chronology: train_start < train_end < test_start < test_end
        assert w.train_start < w.train_end
        assert w.train_end <= w.test_start
        assert w.test_start < w.test_end

    # Aggregate performance exists
    assert result.aggregate_metrics is not None
    assert len(result.combined_equity_curve) > 0
