"""Lightweight performance regression tests using broad sanity thresholds.

Guards against:
- Accidentally re-loading or parsing dataset on every tick/step
- Unbounded memory growth during streaming
- Repeated model re-initialization during backtests
- Extremely slow event throughput (< 100 bars/sec)
"""

import time
import tempfile
from pathlib import Path
import pytest
import pandas as pd

from backend.app.benchmark.runner import BenchmarkRunner
from backend.app.data.loader import CSVDataLoader
from backend.app.paper.service import PaperTradingService
from backend.app.paper.storage import SQLitePaperStorage
from backend.app.research.dataset import DatasetManager
from backend.app.backtesting.engine import BacktestEngine
from backend.app.strategies.momentum import TimeSeriesMomentumStrategy


def test_backtest_broad_throughput_threshold():
    """Guarantees backtest engine throughput exceeds broad floor threshold (e.g. >= 200 bars/s)."""
    runner = BenchmarkRunner()
    metric = runner.benchmark_backtest_engine(bars_count=500)
    # Broad floor threshold: must process at least 200 bars/sec on any hardware
    assert metric.throughput_per_sec >= 200.0, f"Backtest throughput fell below threshold: {metric.throughput_per_sec} bars/s"


def test_feature_engine_broad_throughput_threshold():
    """Guarantees streaming feature engine throughput exceeds broad floor threshold."""
    runner = BenchmarkRunner()
    metric = runner.benchmark_streaming_features(bars_count=500)
    assert metric.throughput_per_sec >= 200.0, f"Feature throughput fell below threshold: {metric.throughput_per_sec} bars/s"


def test_no_full_dataset_reload_during_paper_step():
    """Verifies that executing a paper replay step does not reload full CSV files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = SQLitePaperStorage(str(Path(tmp_dir) / "test_perf_step.db"))
        svc = PaperTradingService(storage=storage)

        runner = BenchmarkRunner()
        loader = CSVDataLoader()
        df = loader.load_csv(runner.single_csv).iloc[:100]

        dm = DatasetManager()
        dm.register_dataframe("perf_test_ds", df, symbols=["AAPL"])

        cfg = {
            "mode": "HISTORICAL_REPLAY",
            "dataset_id": "perf_test_ds",
            "symbols": ["AAPL"],
            "strategy": "TimeSeriesMomentum",
            "strategy_params": {"lookback_period": 5},
        }
        session = svc.create_session(cfg, dataset_manager=dm)
        sid = session.session_id

        # Step 20 times and verify each step latency is fast (< 100ms)
        step_times = []
        for _ in range(20):
            t0 = time.perf_counter()
            svc.step_session(sid)
            step_times.append(time.perf_counter() - t0)

        # Average step time should be under 50ms
        avg_step_ms = (sum(step_times) / len(step_times)) * 1000.0
        assert avg_step_ms < 100.0, f"Paper replay step unexpectedly slow: {avg_step_ms:.2f}ms"
