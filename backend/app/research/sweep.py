"""Lightweight deterministic parameter sweep service with overfitting safeguards."""

from __future__ import annotations
import itertools
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import copy

from backend.app.research.config import ExperimentConfig
from backend.app.research.runner import ExperimentRunner
from backend.app.research.splits import chronological_split


@dataclass
class SweepLeaderboardEntry:
    parameters: Dict[str, Any]
    experiment_id: str
    configuration_hash: str
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    total_return: Optional[float]
    maximum_drawdown: Optional[float]
    win_rate: Optional[float]
    profit_factor: Optional[float]
    trade_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "parameters": self.parameters,
            "experiment_id": self.experiment_id,
            "configuration_hash": self.configuration_hash,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "total_return": self.total_return,
            "maximum_drawdown": self.maximum_drawdown,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "trade_count": self.trade_count,
        }


@dataclass
class SweepResult:
    """Structured result of a grid parameter sweep."""

    strategy_name: str
    total_combinations: int
    eval_split_used: str
    test_quarantine_enforced: bool
    leaderboard: List[Dict[str, Any]]
    best_by_sharpe: Optional[Dict[str, Any]] = None
    best_by_return: Optional[Dict[str, Any]] = None
    best_by_drawdown: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "total_combinations": self.total_combinations,
            "eval_split_used": self.eval_split_used,
            "test_quarantine_enforced": self.test_quarantine_enforced,
            "leaderboard": self.leaderboard,
            "best_by_sharpe": self.best_by_sharpe,
            "best_by_return": self.best_by_return,
            "best_by_drawdown": self.best_by_drawdown,
        }


class ParameterSweepRunner:
    """Orchestrates deterministic parameter sweeps across discrete strategy configurations."""

    def __init__(self, runner: Optional[ExperimentRunner] = None):
        self.runner = runner or ExperimentRunner()

    @staticmethod
    def expand_grid(param_grid: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
        """Expands parameter dict into list of deterministic parameter combinations."""
        sorted_keys = sorted(param_grid.keys())
        values_product = itertools.product(*(param_grid[k] for k in sorted_keys))
        combinations = []
        for values in values_product:
            combinations.append(dict(zip(sorted_keys, values)))
        return combinations

    def run_sweep(
        self,
        base_config: ExperimentConfig,
        parameter_grid: Dict[str, List[Any]],
        eval_split: str = "train",  # "train", "val", "all"
        train_pct: float = 0.60,
        val_pct: float = 0.20,
        test_pct: float = 0.20,
    ) -> SweepResult:
        """Executes parameter sweep over all grid combinations.
        
        Overfitting Safeguard:
        By default, sweeps run exclusively on the 'train' (or 'val') split.
        The 'test' split is strictly isolated to prevent data leakage and p-hacking.
        """
        if eval_split == "test":
            raise ValueError(
                "Overfitting safeguard violation: Parameter tuning directly on the 'test' split "
                "is forbidden to prevent data snooping. Use eval_split='train' or 'val'."
            )

        combinations = self.expand_grid(parameter_grid)
        dataset_id = base_config.dataset.dataset_id or base_config.dataset.symbols[0]

        # 1. Apply chronological partition if eval_split is train or val
        if eval_split in ("train", "val"):
            full_df = self.runner.dataset_manager.load_dataset(dataset_id)
            splits = chronological_split(full_df, train_pct=train_pct, val_pct=val_pct, test_pct=test_pct)
            target_df = splits.train_df if eval_split == "train" else splits.val_df
            active_dataset_id = f"{dataset_id}_{eval_split}"
            self.runner.dataset_manager.register_in_memory_dataset(
                dataset_id=active_dataset_id,
                df=target_df,
                symbols=base_config.dataset.symbols,
            )
            test_quarantined = True
        else:
            active_dataset_id = dataset_id
            test_quarantined = False

        # 2. Iterate through all combinations deterministically
        leaderboard_entries: List[SweepLeaderboardEntry] = []

        for combo in combinations:
            cfg_dict = copy.deepcopy(base_config.to_dict())
            cfg_dict["dataset"]["dataset_id"] = active_dataset_id
            # Merge base parameters with grid combination
            merged_params = copy.deepcopy(cfg_dict["strategy"]["parameters"])
            merged_params.update(combo)
            cfg_dict["strategy"]["parameters"] = merged_params

            cfg = ExperimentConfig.from_dict(cfg_dict)
            try:
                res = self.runner.run_experiment(cfg)
                m = res.metrics or {}
                entry = SweepLeaderboardEntry(
                    parameters=combo,
                    experiment_id=res.experiment_id,
                    configuration_hash=res.configuration_hash,
                    sharpe_ratio=m.get("sharpe_ratio"),
                    sortino_ratio=m.get("sortino_ratio"),
                    total_return=m.get("total_return"),
                    maximum_drawdown=m.get("maximum_drawdown"),
                    win_rate=m.get("win_rate"),
                    profit_factor=m.get("profit_factor"),
                    trade_count=int(m.get("number_of_trades", 0)),
                )
                leaderboard_entries.append(entry)
            except Exception as e:
                # Still record failed combination with None metrics
                entry = SweepLeaderboardEntry(
                    parameters=combo,
                    experiment_id=f"failed_{cfg.get_hash()[:8]}",
                    configuration_hash=cfg.get_hash(),
                    sharpe_ratio=None,
                    sortino_ratio=None,
                    total_return=None,
                    maximum_drawdown=None,
                    win_rate=None,
                    profit_factor=None,
                    trade_count=0,
                )
                leaderboard_entries.append(entry)

        # 3. Sort leaderboard by Sharpe ratio descending
        sorted_entries = sorted(
            leaderboard_entries,
            key=lambda x: (x.sharpe_ratio is not None, x.sharpe_ratio or -999.0),
            reverse=True,
        )

        # Identify best by multiple financial dimensions (not just total return)
        valid_entries = [e for e in leaderboard_entries if e.sharpe_ratio is not None]
        best_by_sharpe = max(valid_entries, key=lambda x: x.sharpe_ratio or -999.0).to_dict() if valid_entries else None
        best_by_return = max(valid_entries, key=lambda x: x.total_return or -999.0).to_dict() if valid_entries else None
        best_by_drawdown = min(valid_entries, key=lambda x: x.maximum_drawdown or 999.0).to_dict() if valid_entries else None

        return SweepResult(
            strategy_name=base_config.strategy.name,
            total_combinations=len(combinations),
            eval_split_used=eval_split,
            test_quarantine_enforced=test_quarantined,
            leaderboard=[e.to_dict() for e in sorted_entries],
            best_by_sharpe=best_by_sharpe,
            best_by_return=best_by_return,
            best_by_drawdown=best_by_drawdown,
        )
