"""Modular software performance benchmarking engine for AlgoTrade.

Evaluates:
1. Dataset I/O throughput (CSV loading, parsing, normalization)
2. Streaming Feature Engine calculation throughput
3. Strategy signal generation latency and throughput
4. Event-driven BacktestEngine throughput (bars/sec)
5. Paper trading replay loop throughput (bars/sec, events/sec)
6. WebSocket event serialization throughput
7. Peak memory delta via tracemalloc

STRICT INVARIANT: Software performance evaluation only. Never claims profitability.
"""

from __future__ import annotations
import time
import json
import tracemalloc
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd

from backend.app.data.loader import CSVDataLoader, OHLCVBar, MarketSnapshot
from backend.app.ml.features import FeatureEngineer, FeatureConfig
from backend.app.paper.streaming_features import StreamingFeatureEngine
from backend.app.strategies.momentum import TimeSeriesMomentumStrategy
from backend.app.strategies.mean_reversion import MeanReversionStrategy
from backend.app.backtesting.engine import BacktestEngine
from backend.app.paper.service import PaperTradingService
from backend.app.paper.storage import SQLitePaperStorage
from backend.app.paper.events import MarketEvent, FillExecutionEvent


@dataclass
class MetricSummary:
    name: str
    runtime_ms: float
    items_processed: int
    throughput_per_sec: float
    peak_memory_kb: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "runtime_ms": round(self.runtime_ms, 2),
            "items_processed": self.items_processed,
            "throughput_per_sec": round(self.throughput_per_sec, 2),
            "peak_memory_kb": round(self.peak_memory_kb, 2),
            "metadata": self.metadata,
        }


@dataclass
class BenchmarkReport:
    timestamp: str
    total_runtime_s: float
    metrics: List[MetricSummary]
    system_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_runtime_s": round(self.total_runtime_s, 3),
            "metrics": [m.to_dict() for m in self.metrics],
            "system_info": self.system_info,
        }

    def print_summary(self) -> None:
        print("\n" + "=" * 78)
        print("          AlgoTrade Quantitative Engine -- Software Performance Benchmark")
        print("=" * 78)
        print(f" Timestamp: {self.timestamp} | Total Runtime: {self.total_runtime_s:.2f}s")
        print("-" * 78)
        header = f"{'Benchmark Task':<32} | {'Processed':<10} | {'Runtime (ms)':<12} | {'Throughput':<12} | {'Peak Mem'}"
        print(header)
        print("-" * 78)
        for m in self.metrics:
            unit = m.metadata.get("unit", "items/s")
            line = f"{m.name:<32} | {m.items_processed:<10} | {m.runtime_ms:>10.2f}ms | {m.throughput_per_sec:>9.1f} {unit:<2} | {m.peak_memory_kb:>8.1f} KB"
            print(line)
        print("=" * 78)
        print(" NOTE: Results evaluate algorithmic software execution performance only.")
        print("=" * 78 + "\n")


class BenchmarkRunner:
    """Executes standardized software engineering benchmarks across the platform."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.base_data_dir = data_dir or (Path(__file__).resolve().parent.parent.parent.parent / "data" / "demo")
        self.single_csv = self.base_data_dir / "benchmark_single_asset.csv"
        self.multi_csv = self.base_data_dir / "benchmark_multi_asset.csv"
        
        # Fallback to AAPL_sample if benchmark files not yet generated
        if not self.single_csv.exists():
            from backend.app.benchmark.generate_data import generate_benchmark_datasets
            generate_benchmark_datasets(self.base_data_dir)

    def benchmark_dataset_loading(self, iterations: int = 5) -> MetricSummary:
        """Benchmarks raw CSV ingestion and normalization."""
        loader = CSVDataLoader()
        tracemalloc.start()
        t0 = time.perf_counter()
        
        total_rows = 0
        for _ in range(iterations):
            df = loader.load_csv(self.single_csv)
            total_rows += len(df)
            
        elapsed = time.perf_counter() - t0
        _, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        throughput = total_rows / elapsed if elapsed > 0 else 0.0
        return MetricSummary(
            name="Dataset CSV Loading",
            runtime_ms=elapsed * 1000.0,
            items_processed=total_rows,
            throughput_per_sec=throughput,
            peak_memory_kb=peak_mem / 1024.0,
            metadata={"unit": "rows/s", "file": self.single_csv.name, "iterations": iterations},
        )

    def benchmark_streaming_features(self, bars_count: int = 2000) -> MetricSummary:
        """Benchmarks incremental StreamingFeatureEngine ring-buffer calculations."""
        loader = CSVDataLoader()
        df = loader.load_csv(self.single_csv)
        bars = loader.to_bars(df, symbol="AAPL")[:bars_count]
        
        feat_engine = StreamingFeatureEngine(symbols=["AAPL"], max_buffer_size=200)
        tracemalloc.start()
        t0 = time.perf_counter()
        
        for bar in bars:
            feat_engine.update_bar(bar)
            _ = feat_engine.get_history_df("AAPL")
            
        elapsed = time.perf_counter() - t0
        _, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        throughput = len(bars) / elapsed if elapsed > 0 else 0.0
        return MetricSummary(
            name="Streaming Feature Engine",
            runtime_ms=elapsed * 1000.0,
            items_processed=len(bars),
            throughput_per_sec=throughput,
            peak_memory_kb=peak_mem / 1024.0,
            metadata={"unit": "bars/s", "buffer_size": 200},
        )

    def benchmark_strategy_evaluation(self, bars_count: int = 2000) -> MetricSummary:
        """Benchmarks strategy signal generation throughput over incremental slices."""
        loader = CSVDataLoader()
        df = loader.load_csv(self.single_csv)
        bars = loader.to_bars(df, symbol="AAPL")[:bars_count]
        
        strat = TimeSeriesMomentumStrategy(symbol="AAPL", parameters={"lookback_period": 20})
        clean_df = df.iloc[:bars_count]
        
        tracemalloc.start()
        t0 = time.perf_counter()
        
        signals_emitted = 0
        for i in range(20, len(bars)):
            h_slice = clean_df.iloc[: i + 1]
            sig = strat.generate_signal(bars[i], h_slice)
            if sig:
                signals_emitted += 1
                
        elapsed = time.perf_counter() - t0
        _, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        evaluated = len(bars) - 20
        throughput = evaluated / elapsed if elapsed > 0 else 0.0
        return MetricSummary(
            name="Strategy Signal Generation",
            runtime_ms=elapsed * 1000.0,
            items_processed=evaluated,
            throughput_per_sec=throughput,
            peak_memory_kb=peak_mem / 1024.0,
            metadata={"unit": "eval/s", "signals_emitted": signals_emitted},
        )

    def benchmark_backtest_engine(self, bars_count: int = 3000) -> MetricSummary:
        """Benchmarks complete event-driven BacktestEngine execution."""
        strat = TimeSeriesMomentumStrategy(symbol="AAPL", parameters={"lookback_period": 10})
        engine = BacktestEngine(
            symbol="AAPL",
            initial_capital=100_000.0,
            commission_fixed=1.0,
            commission_percent=0.0005,
            slippage_bps=5.0,
        )
        loader = CSVDataLoader()
        df = loader.load_csv(self.single_csv).iloc[:bars_count]
        
        tracemalloc.start()
        t0 = time.perf_counter()
        result = engine.run(strategy=strat, df=df)
        elapsed = time.perf_counter() - t0
        _, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        bars_run = len(result.equity_curve)
        throughput = bars_run / elapsed if elapsed > 0 else 0.0
        return MetricSummary(
            name="Event-Driven Backtest",
            runtime_ms=elapsed * 1000.0,
            items_processed=bars_run,
            throughput_per_sec=throughput,
            peak_memory_kb=peak_mem / 1024.0,
            metadata={"unit": "bars/s", "trades": len(result.trades)},
        )

    def benchmark_paper_replay(self, bars_count: int = 500) -> MetricSummary:
        """Benchmarks step-by-step paper replay simulation with risk and ledger updates."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "bench_paper.db"
            storage = SQLitePaperStorage(db_path)
            svc = PaperTradingService(storage=storage)
            
            cfg = {
                "dataset_id": "benchmark_single_asset",
                "symbols": ["AAPL"],
                "strategy": "TimeSeriesMomentum",
                "strategy_params": {"lookback_period": 5},
                "initial_capital": 100_000.0,
            }
            
            # Register in-memory data for session
            loader = CSVDataLoader()
            df = loader.load_csv(self.single_csv).iloc[:bars_count]
            from backend.app.research.dataset import DatasetManager
            dm = DatasetManager()
            dm.register_dataframe("benchmark_single_asset", df, symbols=["AAPL"])
            
            session = svc.create_session(cfg, dataset_manager=dm)
            sid = session.session_id
            
            tracemalloc.start()
            t0 = time.perf_counter()
            
            total_events = 0
            steps = 0
            while svc.providers[sid].has_next():
                sess, evts = svc.step_session(sid)
                steps += 1
                total_events += len(evts)
                if steps >= bars_count:
                    break
                    
            elapsed = time.perf_counter() - t0
            _, peak_mem = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            
            throughput = steps / elapsed if elapsed > 0 else 0.0
            return MetricSummary(
                name="Paper Trading Step Replay",
                runtime_ms=elapsed * 1000.0,
                items_processed=steps,
                throughput_per_sec=throughput,
                peak_memory_kb=peak_mem / 1024.0,
                metadata={"unit": "bars/s", "events_emitted": total_events},
            )

    def benchmark_websocket_serialization(self, event_count: int = 5000) -> MetricSummary:
        """Benchmarks serialization of paper events into JSON WebSocket transport payloads."""
        evt = MarketEvent(
            timestamp="2026-09-22T10:00:00Z",
            event_type="MARKET_BAR",
            session_id="paper_bench_001",
            symbol="AAPL",
            open=150.0,
            high=152.0,
            low=149.5,
            close=151.2,
            volume=50000.0,
            bar_index=100,
            total_bars=1000,
        )
        
        tracemalloc.start()
        t0 = time.perf_counter()
        
        for _ in range(event_count):
            d = evt.to_dict()
            _ = json.dumps(d)
            
        elapsed = time.perf_counter() - t0
        _, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        throughput = event_count / elapsed if elapsed > 0 else 0.0
        return MetricSummary(
            name="WebSocket Event Serialization",
            runtime_ms=elapsed * 1000.0,
            items_processed=event_count,
            throughput_per_sec=throughput,
            peak_memory_kb=peak_mem / 1024.0,
            metadata={"unit": "events/s"},
        )

    def run_all(self, bars_count: int = 1000) -> BenchmarkReport:
        """Executes full benchmark suite and returns consolidated report."""
        t_start = time.perf_counter()
        metrics: List[MetricSummary] = []
        
        metrics.append(self.benchmark_dataset_loading())
        metrics.append(self.benchmark_streaming_features(bars_count=bars_count))
        metrics.append(self.benchmark_strategy_evaluation(bars_count=bars_count))
        metrics.append(self.benchmark_backtest_engine(bars_count=bars_count))
        metrics.append(self.benchmark_paper_replay(bars_count=min(500, bars_count)))
        metrics.append(self.benchmark_websocket_serialization(event_count=3000))
        
        total_time = time.perf_counter() - t_start
        from datetime import datetime, timezone
        import platform
        
        report = BenchmarkReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_runtime_s=total_time,
            metrics=metrics,
            system_info={
                "python_version": platform.python_version(),
                "system": platform.system(),
                "machine": platform.machine(),
            },
        )
        return report
