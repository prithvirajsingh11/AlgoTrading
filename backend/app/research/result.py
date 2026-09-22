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

    def to_markdown(self) -> str:
        """Generates a clean, reproducible markdown report for institutional evaluation."""
        m = self.metrics or {}
        cfg = self.config or {}
        ds_cfg = cfg.get("dataset", {})
        strat_cfg = cfg.get("strategy", {})
        exec_cfg = cfg.get("execution", {})
        risk_cfg = cfg.get("risk", {})
        port_cfg = cfg.get("portfolio", {})
        stats = self.execution_statistics or {}

        lines = [
            f"# Quantitative Research Experiment Report: `{self.experiment_id}`",
            "",
            "> **Institutional Notice**: This experiment was executed within AlgoTrade's discrete-event simulation engine. All trades are simulated with modeled transaction costs and zero lookahead bias. Zero live brokerage connections or real monetary orders.",
            "",
            "## 1. Experiment Overview & Reproducibility",
            "",
            f"- **Experiment ID**: `{self.experiment_id}`",
            f"- **Reproducibility Hash (SHA-256)**: `{self.configuration_hash}`",
            f"- **Execution Date**: `{self.created_at}`",
            f"- **Runtime**: `{stats.get('runtime_ms', 0):.2f} ms`",
            f"- **Total Bars Processed**: `{stats.get('total_bars', 0)}`",
            "",
            "## 2. Research Configuration & Execution Assumptions",
            "",
            "### Dataset & Strategy",
            f"- **Dataset**: `{ds_cfg.get('dataset_id', 'Unknown')}`",
            f"- **Symbols**: `{', '.join(ds_cfg.get('symbols', ['Unknown']))}`",
            f"- **Strategy**: `{strat_cfg.get('name', 'Unknown')}`",
            f"- **Parameters**: `{json.dumps(strat_cfg.get('parameters', {}))}`",
            "",
            "### Portfolio & Execution Mechanics",
            f"- **Initial Capital**: `${port_cfg.get('initial_capital', 100000.0):,.2f}`",
            f"- **Fixed Commission**: `${exec_cfg.get('commission_fixed', 0.0):.2f}` per fill",
            f"- **Percentage Commission**: `{exec_cfg.get('commission_percent', 0.0) * 10000:.1f} bps`",
            f"- **Execution Slippage**: `{exec_cfg.get('slippage_bps', 0.0):.1f} bps`",
            "",
            "### Risk & Concentration Limits",
            f"- **Position Sizing**: `{risk_cfg.get('position_size_pct', 0.20):.1%} of equity`",
            f"- **Maximum Concentration**: `{risk_cfg.get('max_position_pct', 0.50):.1%}`",
            f"- **Max Drawdown Circuit Breaker**: `{risk_cfg.get('max_drawdown_limit', 0.25):.1%}`",
            "",
            "## 3. Quantitative Performance Metrics",
            "",
            "| Metric | Value |",
            "| :--- | :--- |",
            f"| **Total Return** | `{m.get('total_return', 0.0):.2%}` |",
            f"| **Annualized Return** | `{m.get('annualized_return', 0.0):.2%}` |",
            f"| **Sharpe Ratio** | `{m.get('sharpe_ratio', 0.0):.4f}` |",
            f"| **Sortino Ratio** | `{m.get('sortino_ratio', 0.0):.4f}` |",
            f"| **Max Drawdown** | `{m.get('maximum_drawdown', 0.0):.2%}` |",
            f"| **Win Rate** | `{m.get('win_rate', 0.0):.2%}` |",
            f"| **Profit Factor** | `{m.get('profit_factor', 0.0):.2f}` |",
            f"| **Executed Trades** | `{stats.get('trade_count', len(self.trade_records))}` |",
            "",
            "## 4. Trade Execution Blotter Summary",
            "",
        ]

        if self.trade_records:
            lines.append("| Timestamp | Symbol | Side | Quantity | Price | P&L |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for t in self.trade_records[:15]:
                ts = t.get("timestamp", "")[:19]
                sym = t.get("symbol", "")
                side = t.get("side", "")
                q = t.get("quantity", 0)
                p = t.get("price", t.get("fill_price", 0.0))
                pnl = t.get("pnl", 0.0)
                lines.append(f"| {ts} | {sym} | {side} | {q} | ${p:.2f} | ${pnl:+.2f} |")
            if len(self.trade_records) > 15:
                lines.append(f"\n*(Truncated: {len(self.trade_records)} total trades)*")
        else:
            lines.append("*No trades triggered during this simulation interval.*")

        if self.warnings:
            lines.extend(["", "## 5. Experiment Warnings", ""])
            for w in self.warnings:
                lines.append(f"- ⚠️ {w}")

        return "\n".join(lines) + "\n"
