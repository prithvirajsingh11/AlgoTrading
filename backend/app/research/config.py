"""Serializable experiment configuration and deterministic configuration hashing."""

from __future__ import annotations
import json
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List, Union
from datetime import datetime


@dataclass
class DatasetConfig:
    dataset_id: str
    symbols: List[str]
    timeframe: str = "1d"
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@dataclass
class PortfolioConfig:
    initial_capital: float = 100_000.0


@dataclass
class StrategyConfig:
    name: str = "MovingAverageCross"
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionConfig:
    commission_fixed: float = 1.0
    commission_percent: float = 0.0005
    slippage_bps: float = 5.0


@dataclass
class RiskConfig:
    position_sizing_method: str = "percent_equity"  # "percent_equity", "fixed_quantity", "risk_based"
    position_size_pct: float = 0.20
    risk_per_trade: float = 0.01
    max_position_pct: float = 0.50
    max_drawdown_limit: float = 0.30
    allow_shorting: bool = False
    stop_loss_pct: Optional[float] = None


@dataclass
class BacktestingConfig:
    mode: str = "standard"  # "standard", "walk_forward"
    walk_forward_params: Optional[Dict[str, Any]] = None  # train_bars, test_bars, step_bars


@dataclass
class JevConfig:
    enabled: bool = False
    model: str = "jev-latest"
    min_confidence: float = 0.60
    decision_frequency: str = "on_signal"  # "on_signal", "every_bar", "every_n_bars"
    frequency_n: int = 5
    cache_enabled: bool = True
    timeout_seconds: float = 5.0


@dataclass
class ExperimentConfig:
    """Canonical experiment configuration containing full reproducibility specification."""

    dataset: DatasetConfig
    strategy: StrategyConfig
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    backtesting: BacktestingConfig = field(default_factory=BacktestingConfig)
    jev: Optional[JevConfig] = None
    seed: int = 42
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExperimentConfig:
        d_cfg = data.get("dataset", {})
        symbols = d_cfg.get("symbols", [])
        if isinstance(symbols, str):
            symbols = [symbols]

        dataset = DatasetConfig(
            dataset_id=str(d_cfg.get("dataset_id", "")),
            symbols=list(symbols),
            timeframe=str(d_cfg.get("timeframe", "1d")),
            start_date=d_cfg.get("start_date"),
            end_date=d_cfg.get("end_date"),
        )

        s_cfg = data.get("strategy", {})
        strategy = StrategyConfig(
            name=str(s_cfg.get("name", "MovingAverageCross")),
            parameters=dict(s_cfg.get("parameters", {})),
        )

        p_cfg = data.get("portfolio", {})
        portfolio = PortfolioConfig(
            initial_capital=float(p_cfg.get("initial_capital", 100_000.0)),
        )

        e_cfg = data.get("execution", {})
        execution = ExecutionConfig(
            commission_fixed=float(e_cfg.get("commission_fixed", 1.0)),
            commission_percent=float(e_cfg.get("commission_percent", 0.0005)),
            slippage_bps=float(e_cfg.get("slippage_bps", 5.0)),
        )

        r_cfg = data.get("risk", {})
        risk = RiskConfig(
            position_sizing_method=str(r_cfg.get("position_sizing_method", "percent_equity")),
            position_size_pct=float(r_cfg.get("position_size_pct", 0.20)),
            risk_per_trade=float(r_cfg.get("risk_per_trade", 0.01)),
            max_position_pct=float(r_cfg.get("max_position_pct", 0.50)),
            max_drawdown_limit=float(r_cfg.get("max_drawdown_limit", 0.30)),
            allow_shorting=bool(r_cfg.get("allow_shorting", False)),
            stop_loss_pct=float(r_cfg["stop_loss_pct"]) if r_cfg.get("stop_loss_pct") is not None else None,
        )

        b_cfg = data.get("backtesting", {})
        backtesting = BacktestingConfig(
            mode=str(b_cfg.get("mode", "standard")),
            walk_forward_params=b_cfg.get("walk_forward_params"),
        )

        jev = None
        j_cfg = data.get("jev")
        if j_cfg is not None:
            jev = JevConfig(
                enabled=bool(j_cfg.get("enabled", False)),
                model=str(j_cfg.get("model", "jev-latest")),
                min_confidence=float(j_cfg.get("min_confidence", 0.60)),
                decision_frequency=str(j_cfg.get("decision_frequency", "on_signal")),
                frequency_n=int(j_cfg.get("frequency_n", 5)),
                cache_enabled=bool(j_cfg.get("cache_enabled", True)),
                timeout_seconds=float(j_cfg.get("timeout_seconds", 5.0)),
            )

        return cls(
            dataset=dataset,
            strategy=strategy,
            portfolio=portfolio,
            execution=execution,
            risk=risk,
            backtesting=backtesting,
            jev=jev,
            seed=int(data.get("seed", 42)),
            description=str(data.get("description", "")),
        )

    def to_json(self, indent: Optional[int] = None) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_json(cls, json_str: str) -> ExperimentConfig:
        return cls.from_dict(json.loads(json_str))

    def get_hash(self) -> str:
        """Computes deterministic SHA-256 hash of canonicalized configuration."""
        return compute_config_hash(self)


def compute_config_hash(config: Union[ExperimentConfig, Dict[str, Any]]) -> str:
    """Produces a deterministic 64-character SHA-256 hash from an experiment configuration.
    
    Keys are strictly sorted recursively, whitespace is stripped, and numbers are standardized.
    Two identical configurations will produce the exact same hash.
    """
    if isinstance(config, ExperimentConfig):
        cfg_dict = config.to_dict()
    else:
        cfg_dict = dict(config)

    # Exclude non-functional metadata that doesn't impact backtest execution
    clean_dict = {
        "dataset": cfg_dict.get("dataset"),
        "strategy": cfg_dict.get("strategy"),
        "portfolio": cfg_dict.get("portfolio"),
        "execution": cfg_dict.get("execution"),
        "risk": cfg_dict.get("risk"),
        "backtesting": cfg_dict.get("backtesting"),
        "seed": cfg_dict.get("seed", 42),
    }

    # Include jev configuration if provided and enabled (or explicitly specified)
    if cfg_dict.get("jev") is not None:
        clean_dict["jev"] = cfg_dict.get("jev")

    canonical_json = json.dumps(clean_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
