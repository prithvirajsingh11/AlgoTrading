"""Quantitative research and reproducibility platform."""

from backend.app.research.dataset import DatasetMetadata, DatasetManager
from backend.app.research.validator import DatasetValidator, ValidationReport
from backend.app.research.config import (
    ExperimentConfig,
    DatasetConfig,
    StrategyConfig,
    ExecutionConfig,
    RiskConfig,
    BacktestingConfig,
    compute_config_hash,
)
from backend.app.research.result import ExperimentResult, DrawdownPoint
from backend.app.research.splits import SplitResult, chronological_split
from backend.app.research.storage import BaseExperimentStorage, SQLiteExperimentStorage
from backend.app.research.runner import ExperimentRunner, STRATEGY_REGISTRY
from backend.app.research.sweep import ParameterSweepRunner, SweepResult

__all__ = [
    "DatasetMetadata",
    "DatasetManager",
    "DatasetValidator",
    "ValidationReport",
    "ExperimentConfig",
    "DatasetConfig",
    "StrategyConfig",
    "ExecutionConfig",
    "RiskConfig",
    "BacktestingConfig",
    "compute_config_hash",
    "ExperimentResult",
    "DrawdownPoint",
    "SplitResult",
    "chronological_split",
    "BaseExperimentStorage",
    "SQLiteExperimentStorage",
    "ExperimentRunner",
    "STRATEGY_REGISTRY",
    "ParameterSweepRunner",
    "SweepResult",
]
