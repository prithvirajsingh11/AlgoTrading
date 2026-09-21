"""Structured experiment result object capturing full performance and visualization artifacts."""

from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
from backend.app.research.config import ExperimentConfig


@dataclass
class DrawdownPoint:
    timestamp: str
    equity: float
    high_watermark: float
    drawdown_pct: float

    def to_dict(self) -> Dict[str, Union[str, float]]:
        return {
            "timestamp": self.timestamp,
            "equity": round(self.equity, 2),
            "high_watermark": round(self.high_watermark, 2),
            "drawdown_pct": round(self.drawdown_pct, 4),
        }


@dataclass
class ExperimentResult:
    """Comprehensive, fully serializable quantitative experiment result."""

    experiment_id: str
    configuration_hash: str
    config: Dict[str, Any]
    dataset_metadata: Dict[str, Any]
    strategy_info: Dict[str, Any]
    metrics: Dict[str, Any]
    trade_records: List[Dict[str, Any]]
    equity_curve: List[Dict[str, Any]]
    drawdown_curve: List[Dict[str, Any]]
    execution_statistics: Dict[str, Any]
    walk_forward_results: Optional[Dict[str, Any]] = None
    ai_decision_stats: Optional[Dict[str, Any]] = None
    classification_metrics: Optional[Dict[str, Any]] = None
    feature_importance: Optional[Dict[str, float]] = None
    warnings: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "configuration_hash": self.configuration_hash,
            "config": self.config,
            "dataset_metadata": self.dataset_metadata,
            "strategy_info": self.strategy_info,
            "metrics": self.metrics,
            "trade_records": self.trade_records,
            "equity_curve": self.equity_curve,
            "drawdown_curve": self.drawdown_curve,
            "execution_statistics": self.execution_statistics,
            "walk_forward_results": self.walk_forward_results,
            "ai_decision_stats": self.ai_decision_stats,
            "classification_metrics": self.classification_metrics,
            "feature_importance": self.feature_importance,
            "warnings": self.warnings,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExperimentResult:
        return cls(
            experiment_id=str(data["experiment_id"]),
            configuration_hash=str(data["configuration_hash"]),
            config=dict(data.get("config", {})),
            dataset_metadata=dict(data.get("dataset_metadata", {})),
            strategy_info=dict(data.get("strategy_info", {})),
            metrics=dict(data.get("metrics", {})),
            trade_records=list(data.get("trade_records", [])),
            equity_curve=list(data.get("equity_curve", [])),
            drawdown_curve=list(data.get("drawdown_curve", [])),
            execution_statistics=dict(data.get("execution_statistics", {})),
            walk_forward_results=data.get("walk_forward_results"),
            ai_decision_stats=data.get("ai_decision_stats"),
            classification_metrics=data.get("classification_metrics"),
            feature_importance=data.get("feature_importance"),
            warnings=list(data.get("warnings", [])),
            created_at=str(data.get("created_at", "")),
            completed_at=str(data.get("completed_at", "")),
        )

    def to_json(self, indent: Optional[int] = None) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> ExperimentResult:
        return cls.from_dict(json.loads(json_str))
