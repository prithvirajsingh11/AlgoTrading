"""Command Line Interface for AlgoTrade quantitative research platform.

Usage:
  python -m backend.app.cli run-experiment <config_file>
  python -m backend.app.cli list-datasets
  python -m backend.app.cli validate-dataset <dataset_id>
  python -m backend.app.cli sweep <config_file> --grid <grid_json>
"""

from __future__ import annotations
import sys
import json
import argparse
from pathlib import Path

from backend.app.research.config import ExperimentConfig
from backend.app.research.runner import ExperimentRunner
from backend.app.research.dataset import DatasetManager
from backend.app.research.validator import DatasetValidator
from backend.app.research.sweep import ParameterSweepRunner


def run_experiment_command(config_path_str: str) -> int:
    config_path = Path(config_path_str)
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        return 1

    content = config_path.read_text(encoding="utf-8")
    try:
        config_data = json.loads(content)
        config = ExperimentConfig.from_dict(config_data)
    except Exception as e:
        print(f"Error parsing experiment configuration: {e}")
        return 1

    print(f"=== Running Experiment: {config.strategy.name} on {config.dataset.dataset_id} ===")
    runner = ExperimentRunner()
    try:
        result = runner.run_experiment(config)
    except Exception as e:
        print(f"Experiment execution failed: {e}")
        return 1

    print("\n--- Execution Summary ---")
    print(f"Experiment ID   : {result.experiment_id}")
    print(f"Config Hash     : {result.configuration_hash[:16]}...")
    print(f"Runtime (ms)    : {result.execution_statistics.get('runtime_ms')}")
    print(f"Total Bars      : {result.execution_statistics.get('total_bars')}")
    print(f"Total Trades    : {result.execution_statistics.get('trade_count')}")

    print("\n--- Quantitative Metrics ---")
    m = result.metrics or {}
    print(f"Total Return    : {m.get('total_return', 0.0):.2%}")
    print(f"Annualized Ret  : {m.get('annualized_return', 0.0):.2%}")
    print(f"Sharpe Ratio    : {m.get('sharpe_ratio', 0.0):.4f}")
    print(f"Sortino Ratio   : {m.get('sortino_ratio', 0.0):.4f}")
    print(f"Max Drawdown    : {m.get('maximum_drawdown', 0.0):.2%}")
    print(f"Win Rate        : {m.get('win_rate', 0.0):.2%}")
    print(f"Profit Factor   : {m.get('profit_factor', 0.0):.2f}")

    if result.warnings:
        print("\n--- Warnings ---")
        for w in result.warnings:
            print(f"  * {w}")

    print("\nExperiment artifacts saved successfully.")
    return 0


def list_datasets_command() -> int:
    manager = DatasetManager()
    datasets = manager.discover_datasets()
    print(f"=== Discovered Datasets ({len(datasets)}) ===")
    if not datasets:
        print("No datasets found in data/raw/")
        return 0

    for d in datasets:
        print(f"- {d.dataset_id:<20} | Symbols: {', '.join(d.symbols):<10} | Rows: {d.row_count:<6} | Source: {d.source}")
    return 0


def validate_dataset_command(dataset_id: str) -> int:
    manager = DatasetManager()
    try:
        df = manager.load_dataset(dataset_id)
    except Exception as e:
        print(f"Error loading dataset '{dataset_id}': {e}")
        return 1

    report = DatasetValidator.validate(df)
    print(f"=== Validation Report: {dataset_id} ===")
    print(f"Valid       : {'PASS' if report.valid else 'FAIL'}")
    print(f"Total Rows  : {report.rows}")

    if report.errors:
        print("\n--- Errors ---")
        for err in report.errors:
            print(f"  [ERROR] {err}")

    if report.warnings:
        print("\n--- Warnings ---")
        for w in report.warnings:
            print(f"  [WARN]  {w}")

    return 0 if report.valid else 1


def sweep_command(config_path_str: str, grid_json_str: str) -> int:
    config_path = Path(config_path_str)
    if not config_path.exists():
        print(f"Error: Config not found: {config_path}")
        return 1

    try:
        config = ExperimentConfig.from_json(config_path.read_text(encoding="utf-8"))
        grid = json.loads(grid_json_str)
    except Exception as e:
        print(f"Error parsing sweep parameters: {e}")
        return 1

    print(f"=== Running Parameter Sweep for {config.strategy.name} ===")
    sweep_runner = ParameterSweepRunner()
    result = sweep_runner.run_sweep(config, grid)

    print(f"\nCompleted {result.total_combinations} combinations on split '{result.eval_split_used}'.")
    print("\n--- Top Leaderboard ---")
    for i, entry in enumerate(result.leaderboard[:5]):
        p_str = ", ".join(f"{k}={v}" for k, v in entry["parameters"].items())
        sh = f"{entry['sharpe_ratio']:.4f}" if entry["sharpe_ratio"] is not None else "N/A"
        ret = f"{entry['total_return']:.2%}" if entry["total_return"] is not None else "N/A"
        dd = f"{entry['maximum_drawdown']:.2%}" if entry["maximum_drawdown"] is not None else "N/A"
        print(f"{i+1}. {p_str:<30} | Sharpe: {sh:<8} | Return: {ret:<8} | MaxDD: {dd:<8}")

    return 0


def jev_status_command() -> int:
    from backend.app.core.config import settings

    is_configured = bool(settings.jev_api_key and settings.jev_api_key.strip())
    status_str = "READY" if (settings.jev_enabled and is_configured) else ("UNCONFIGURED" if not is_configured else "DISABLED")

    print("=== Jev AI Decision Layer Status ===")
    print(f"Enabled         : {'YES' if settings.jev_enabled else 'NO'}")
    print(f"Configured      : {'YES' if is_configured else 'NO (JEV_API_KEY missing)'}")
    print(f"Model           : {settings.jev_model}")
    print(f"Provider Status : {status_str}")
    print(f"Timeout         : {settings.jev_timeout_seconds}s")
    print(f"Min Confidence  : {settings.jev_min_confidence:.2f}")
    return 0


def jev_evaluate_command(context_arg: str) -> int:
    from backend.app.api.routes_ai import get_decision_provider

    context_path = Path(context_arg)
    if context_path.exists():
        raw_text = context_path.read_text(encoding="utf-8")
    else:
        raw_text = context_arg

    try:
        context_data = json.loads(raw_text)
    except Exception as e:
        print(f"Error parsing market context JSON: {e}")
        return 1

    provider = get_decision_provider()
    decision = provider.evaluate(context_data)

    print("=== Jev Decision Evaluation ===")
    print(f"Decision        : {decision.decision.value}")
    print(f"Confidence      : {decision.confidence:.4f}")
    print(f"Model           : {decision.model}")
    print(f"Source          : {decision.source}")
    print(f"Latency         : {decision.latency_ms:.1f}ms")
    print(f"Context Hash    : {decision.context_hash[:16]}...")
    print("Probabilities   :")
    for action, prob in decision.probabilities.items():
        print(f"  * {action:<6} : {prob:.4f}")

    if decision.error:
        print(f"Error           : {decision.error}")

    return 0


def demo_command() -> int:
    import tempfile
    from backend.app.paper.service import PaperTradingService
    from backend.app.paper.storage import SQLitePaperStorage
    from backend.app.research.config import (
        ExperimentConfig,
        DatasetConfig,
        StrategyConfig,
        PortfolioConfig,
        ExecutionConfig,
        RiskConfig,
        BacktestingConfig,
    )

    print("=" * 72)
    print("    AlgoTrade -- Institutional Quant Research & Paper Engine (Demo)")
    print("=" * 72)

    # 1. Dataset validation
    print("\n[1/4] Discovering & Validating Datasets...")
    manager = DatasetManager()
    datasets = manager.discover_datasets()
    if not datasets:
        print("  Error: No datasets discovered.")
        return 1
    target_id = "AAPL_sample" if any(d.dataset_id == "AAPL_sample" for d in datasets) else datasets[0].dataset_id
    df = manager.load_dataset(target_id)
    report = DatasetValidator.validate(df)
    status_str = "PASS" if report.valid else "FAIL"
    print(f"  * Dataset       : {target_id}")
    print(f"  * Total Bars    : {len(df)}")
    print(f"  * Quality Check : {status_str} ({len(report.errors)} errors, {len(report.warnings)} warnings)")

    # 2. Benchmark Strategy Execution
    print("\n[2/4] Executing TimeSeriesMomentum Strategy Backtest...")
    runner = ExperimentRunner()
    cfg_mom = ExperimentConfig(
        dataset=DatasetConfig(dataset_id=target_id, symbols=["AAPL"]),
        strategy=StrategyConfig(name="TimeSeriesMomentum", parameters={"lookback_period": 20, "holding_period": 5}),
        portfolio=PortfolioConfig(initial_capital=100_000.0),
        execution=ExecutionConfig(commission_fixed=1.0, commission_percent=0.0005, slippage_bps=5.0),
        risk=RiskConfig(position_size_pct=0.25, max_position_pct=0.50, max_drawdown_limit=0.25),
        backtesting=BacktestingConfig(mode="standard"),
    )
    res_mom = runner.run_experiment(cfg_mom)
    m = res_mom.metrics or {}
    print(f"  * Runtime       : {res_mom.execution_statistics.get('runtime_ms', 0):.1f} ms")
    print(f"  * Total Return  : {m.get('total_return', 0.0):.2%}")
    print(f"  * Sharpe Ratio  : {m.get('sharpe_ratio', 0.0):.4f}")
    print(f"  * Sortino Ratio : {m.get('sortino_ratio', 0.0):.4f}")
    print(f"  * Max Drawdown  : {m.get('maximum_drawdown', 0.0):.2%}")
    print(f"  * Trades Exec   : {res_mom.execution_statistics.get('trade_count', 0)}")

    # 3. Multi-Strategy Comparative Matrix
    print("\n[3/4] Comparative Strategy Benchmark Matrix...")
    cfg_mr = ExperimentConfig(
        dataset=DatasetConfig(dataset_id=target_id, symbols=["AAPL"]),
        strategy=StrategyConfig(name="MeanReversion", parameters={"lookback_period": 20, "entry_z_score": -1.5, "exit_z_score": 0.0}),
        portfolio=PortfolioConfig(initial_capital=100_000.0),
        execution=ExecutionConfig(commission_fixed=1.0, commission_percent=0.0005, slippage_bps=5.0),
        risk=RiskConfig(position_size_pct=0.25, max_position_pct=0.50, max_drawdown_limit=0.25),
        backtesting=BacktestingConfig(mode="standard"),
    )
    res_mr = runner.run_experiment(cfg_mr)

    cfg_ma = ExperimentConfig(
        dataset=DatasetConfig(dataset_id=target_id, symbols=["AAPL"]),
        strategy=StrategyConfig(name="MovingAverageCross", parameters={"fast_period": 10, "slow_period": 30}),
        portfolio=PortfolioConfig(initial_capital=100_000.0),
        execution=ExecutionConfig(commission_fixed=1.0, commission_percent=0.0005, slippage_bps=5.0),
        risk=RiskConfig(position_size_pct=0.25, max_position_pct=0.50, max_drawdown_limit=0.25),
        backtesting=BacktestingConfig(mode="standard"),
    )
    res_ma = runner.run_experiment(cfg_ma)

    header = f"  {'Strategy':<22} | {'Return':<9} | {'Sharpe':<8} | {'MaxDD':<8} | {'Trades':<6}"
    divider = "  " + "-" * 62
    print(divider)
    print(header)
    print(divider)
    for name, r in [("TimeSeriesMomentum", res_mom), ("MeanReversion", res_mr), ("MovingAverageCross", res_ma)]:
        rm = r.metrics or {}
        ret_s = f"{rm.get('total_return', 0.0):.2%}"
        sh_s = f"{rm.get('sharpe_ratio', 0.0):.2f}"
        dd_s = f"{rm.get('maximum_drawdown', 0.0):.2%}"
        tc = r.execution_statistics.get('trade_count', 0)
        print(f"  {name:<22} | {ret_s:<9} | {sh_s:<8} | {dd_s:<8} | {tc:<6}")
    print(divider)

    # 4. In-Memory Real-Time Paper Trading Replay
    print("\n[4/4] Executing 15-Bar Paper Trading Replay Simulation...")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_db = Path(tmpdir) / "demo_paper.db"
        storage = SQLitePaperStorage(str(tmp_db))
        paper_svc = PaperTradingService(storage=storage)
        session = paper_svc.create_session({
            "dataset_id": target_id,
            "symbols": ["AAPL"],
            "strategy": "TimeSeriesMomentum",
            "initial_capital": 100_000.0,
            "speed": "10x",
        })
        steps = 15
        total_events = 0
        for _ in range(steps):
            _, evts = paper_svc.step_session(session.session_id)
            total_events += len(evts)

        export_data = paper_svc.export_results(session.session_id)
        summ = export_data["summary"]
        print(f"  * Session ID    : {session.session_id}")
        print(f"  * Replayed Bars : {summ['total_bars_replayed']} bars")
        print(f"  * Final Equity  : ${summ['current_equity']:,.2f} (Net: ${summ['net_profit']:+,.2f})")
        print(f"  * Orders Placed : {summ['total_orders']}")
        print(f"  * Trades Closed : {summ['total_trades']}")
        print(f"  * Logged Events : {total_events} events")

    print("\n" + "=" * 72)
    print("  AlgoTrade Demo Completed Successfully! (Exit: 0)")
    print("=" * 72)
    return 0


def benchmark_command(bars: int = 1000) -> int:
    from backend.app.benchmark.runner import BenchmarkRunner
    runner = BenchmarkRunner()
    report = runner.run_all(bars_count=bars)
    report.print_summary()
    return 0


def main(args: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="AlgoTrade Research Platform CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # demo
    subparsers.add_parser("demo", help="Run comprehensive offline research & paper-trading demonstration")

    # benchmark
    bench_parser = subparsers.add_parser("benchmark", help="Run comprehensive software performance benchmarks")
    bench_parser.add_argument("--bars", type=int, default=1000, help="Number of bars to process in throughput benchmarks (default: 1000)")

    # run-experiment
    run_parser = subparsers.add_parser("run-experiment", help="Execute an experiment from config file")
    run_parser.add_argument("config", type=str, help="Path to experiment JSON configuration")

    # list-datasets
    subparsers.add_parser("list-datasets", help="List discovered historical datasets")

    # validate-dataset
    val_parser = subparsers.add_parser("validate-dataset", help="Run structured validation on a dataset")
    val_parser.add_argument("dataset_id", type=str, help="Dataset identifier or symbol")

    # sweep
    swp_parser = subparsers.add_parser("sweep", help="Run a grid parameter sweep")
    swp_parser.add_argument("config", type=str, help="Path to base experiment JSON configuration")
    swp_parser.add_argument("--grid", type=str, required=True, help="JSON string defining parameter grid")

    # jev-status
    subparsers.add_parser("jev-status", help="Display Jev AI decision engine status")

    # jev-evaluate
    eval_parser = subparsers.add_parser("jev-evaluate", help="Evaluate market context through Jev")
    eval_parser.add_argument("context", type=str, help="JSON string or file path containing market context")

    parsed = parser.parse_args(args)

    if parsed.command == "demo":
        return demo_command()
    elif parsed.command == "benchmark":
        return benchmark_command(getattr(parsed, "bars", 1000))
    elif parsed.command == "run-experiment":
        return run_experiment_command(parsed.config)
    elif parsed.command == "list-datasets":
        return list_datasets_command()
    elif parsed.command == "validate-dataset":
        return validate_dataset_command(parsed.dataset_id)
    elif parsed.command == "sweep":
        return sweep_command(parsed.config, parsed.grid)
    elif parsed.command == "jev-status":
        return jev_status_command()
    elif parsed.command == "jev-evaluate":
        return jev_evaluate_command(parsed.context)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
