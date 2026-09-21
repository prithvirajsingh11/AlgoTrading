"""Decoupled quantitative experiment runner.

Executes reproducible research experiments from an ExperimentConfig, orchestrating:
  configuration -> dataset loading -> validation -> backtesting/walk-forward -> metrics -> result serialization
"""

from __future__ import annotations
import time
import random
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Type
import numpy as np
import pandas as pd

from backend.app.research.config import ExperimentConfig
from backend.app.research.result import ExperimentResult
from backend.app.research.dataset import DatasetManager
from backend.app.research.validator import DatasetValidator
from backend.app.research.storage import BaseExperimentStorage, SQLiteExperimentStorage

from backend.app.strategies.base import BaseStrategy
from backend.app.strategies.momentum import MovingAverageCrossStrategy, TimeSeriesMomentumStrategy
from backend.app.strategies.mean_reversion import MeanReversionStrategy
from backend.app.strategies.pairs_trading import PairsTradingStrategy
from backend.app.strategies.ml_strategy import MLStrategy

from backend.app.backtesting.engine import BacktestEngine
from backend.app.backtesting.broker import SimulatedBroker
from backend.app.backtesting.walk_forward import WalkForwardEngine
from backend.app.risk.position_sizing import (
    PercentEquitySizer,
    FixedQuantitySizer,
    RiskBasedPositionSizer,
    BasePositionSizer,
)
from backend.app.risk.risk_manager import RiskManager
from backend.app.ml.train import train_ml_pipeline
from backend.app.ml.features import FeatureConfig
from backend.app.ml.labels import LabelConfig
from backend.app.ml.model import XGBoostModelConfig


STRATEGY_REGISTRY: Dict[str, Type[BaseStrategy]] = {
    "MovingAverageCross": MovingAverageCrossStrategy,
    "TimeSeriesMomentum": TimeSeriesMomentumStrategy,
    "MeanReversion": MeanReversionStrategy,
    "PairsTrading": PairsTradingStrategy,
    "MLStrategy": MLStrategy,
}


class ExperimentRunner:
    """Executes deterministic algorithmic trading research experiments."""

    def __init__(
        self,
        dataset_manager: Optional[DatasetManager] = None,
        storage: Optional[BaseExperimentStorage] = None,
        decision_provider: Optional[Any] = None,
    ):
        self.dataset_manager = dataset_manager or DatasetManager()
        self.storage = storage or SQLiteExperimentStorage()
        self.decision_provider = decision_provider

    def _resolve_position_sizer(self, config: ExperimentConfig) -> BasePositionSizer:
        method = config.risk.position_sizing_method.lower()
        if method == "fixed_quantity":
            return FixedQuantitySizer(quantity=float(config.risk.position_size_pct))
        elif method == "risk_based":
            return RiskBasedPositionSizer(
                risk_percent=config.risk.risk_per_trade,
                max_position_pct=config.risk.max_position_pct,
            )
        else:
            return PercentEquitySizer(percent_equity=config.risk.position_size_pct)

    def run_experiment(self, config: ExperimentConfig) -> ExperimentResult:
        """Executes experiment defined by ExperimentConfig."""
        t_start = time.perf_counter()
        created_at = datetime.now(timezone.utc).isoformat()

        # 1. Deterministic seeding
        seed = config.seed
        random.seed(seed)
        np.random.seed(seed)

        # 2. Dataset loading & metadata
        dataset_id = config.dataset.dataset_id
        symbols = config.dataset.symbols
        primary_symbol = symbols[0] if symbols else "UNKNOWN"

        # Check if multi-asset pairs trading feed
        is_multi_asset = len(symbols) > 1 or config.strategy.name == "PairsTrading"
        if is_multi_asset and len(symbols) >= 2:
            data_dict: Dict[str, pd.DataFrame] = {}
            for sym in symbols[:2]:
                data_dict[sym] = self.dataset_manager.load_dataset(sym)
            raw_data: Any = data_dict
            df_eval = data_dict[symbols[0]]
        else:
            df_eval = self.dataset_manager.load_dataset(dataset_id or primary_symbol)
            raw_data = df_eval

        # Date range filtering if requested
        if config.dataset.start_date:
            if isinstance(raw_data, dict):
                for k in raw_data:
                    raw_data[k] = raw_data[k][raw_data[k]["timestamp"] >= config.dataset.start_date].reset_index(drop=True)
                df_eval = raw_data[symbols[0]]
            else:
                raw_data = raw_data[raw_data["timestamp"] >= config.dataset.start_date].reset_index(drop=True)
                df_eval = raw_data

        if config.dataset.end_date:
            if isinstance(raw_data, dict):
                for k in raw_data:
                    raw_data[k] = raw_data[k][raw_data[k]["timestamp"] <= config.dataset.end_date].reset_index(drop=True)
                df_eval = raw_data[symbols[0]]
            else:
                raw_data = raw_data[raw_data["timestamp"] <= config.dataset.end_date].reset_index(drop=True)
                df_eval = raw_data

        # 3. Validation report
        val_report = DatasetValidator.validate(df_eval)
        warnings = list(val_report.warnings)
        if not val_report.valid:
            warnings.extend([f"Dataset validation error: {err}" for err in val_report.errors])

        # Dataset metadata
        meta = self.dataset_manager.get_dataset_metadata(dataset_id)
        if meta is None:
            st = df_eval["timestamp"].min() if not df_eval.empty else None
            et = df_eval["timestamp"].max() if not df_eval.empty else None
            dataset_meta_dict = {
                "dataset_id": dataset_id or primary_symbol,
                "symbols": symbols,
                "timeframe": config.dataset.timeframe,
                "start_timestamp": st.isoformat() if isinstance(st, (pd.Timestamp, datetime)) else None,
                "end_timestamp": et.isoformat() if isinstance(et, (pd.Timestamp, datetime)) else None,
                "row_count": len(df_eval),
                "source": "csv",
                "validation_status": "valid" if val_report.valid else "invalid",
            }
        else:
            dataset_meta_dict = meta.to_dict()
            dataset_meta_dict["validation_status"] = "valid" if val_report.valid else "invalid"

        # 4. Strategy class lookup
        strat_cls = STRATEGY_REGISTRY.get(config.strategy.name)
        if strat_cls is None:
            raise ValueError(f"Unknown strategy: '{config.strategy.name}'. Available: {list(STRATEGY_REGISTRY.keys())}")

        strat_params = dict(config.strategy.parameters)
        classification_metrics_dict: Optional[Dict[str, Any]] = None
        feature_importance_dict: Optional[Dict[str, float]] = None

        if config.strategy.name == "MLStrategy":
            if not strat_params.get("artifact") and not strat_params.get("artifact_path"):
                ml_cfg = config.ml
                f_cfg = FeatureConfig.from_dict(ml_cfg.features) if ml_cfg and ml_cfg.features else FeatureConfig()
                l_cfg = LabelConfig.from_dict(ml_cfg.label) if ml_cfg and ml_cfg.label else LabelConfig()
                m_cfg = XGBoostModelConfig.from_dict(ml_cfg.hyperparameters) if ml_cfg and ml_cfg.hyperparameters else XGBoostModelConfig(random_seed=config.seed)
                scale_m = ml_cfg.scale_method if ml_cfg else "standard"
                cal_m = ml_cfg.calibration if ml_cfg else "none"

                train_res = train_ml_pipeline(
                    df=df_eval,
                    feature_config=f_cfg,
                    label_config=l_cfg,
                    model_config=m_cfg,
                    scale_method=scale_m,
                    calibration_method=cal_m,
                    symbol=primary_symbol,
                )
                strat_params["artifact"] = train_res.artifact
                if ml_cfg:
                    strat_params["buy_threshold"] = ml_cfg.buy_threshold
                    strat_params["sell_threshold"] = ml_cfg.sell_threshold
                classification_metrics_dict = train_res.test_metrics.to_dict()
                feature_importance_dict = train_res.artifact.feature_importance
            else:
                art = strat_params.get("artifact")
                if art is not None and hasattr(art, "feature_importance"):
                    feature_importance_dict = art.feature_importance

        # 5. Execution mode: standard vs walk_forward
        mode = config.backtesting.mode.lower()
        walk_forward_payload: Optional[Dict[str, Any]] = None
        ai_decision_stats: Optional[Dict[str, Any]] = None

        if mode == "walk_forward":
            wf_params = config.backtesting.walk_forward_params or {}
            train_bars = int(wf_params.get("train_bars", 60))
            test_bars = int(wf_params.get("test_bars", 30))
            step_bars = int(wf_params.get("step_bars", 30))

            wf_engine = WalkForwardEngine(
                symbol=primary_symbol,
                initial_capital=config.portfolio.initial_capital,
                commission_fixed=config.execution.commission_fixed,
                commission_percent=config.execution.commission_percent,
                slippage_bps=config.execution.slippage_bps,
            )

            wf_result = wf_engine.run(
                df=df_eval,
                strategy_class=strat_cls,
                strategy_params=strat_params,
                train_bars=train_bars,
                test_bars=test_bars,
                step_bars=step_bars,
            )

            metrics_dict = wf_result.aggregate_metrics.model_dump()
            equity_curve = wf_result.combined_equity_curve
            trade_records = []
            for w in wf_result.windows:
                trade_records.extend(w.trades)

            walk_forward_payload = {
                "total_windows": wf_result.total_windows,
                "windows": [w.model_dump() for w in wf_result.windows],
            }

        else:
            # Standard backtest mode
            strategy = strat_cls(symbol=primary_symbol, parameters=strat_params)

            broker = SimulatedBroker(
                commission_fixed=config.execution.commission_fixed,
                commission_percent=config.execution.commission_percent,
                slippage_bps=config.execution.slippage_bps,
            )
            risk_manager = RiskManager(
                max_position_pct=config.risk.max_position_pct,
                max_drawdown_limit=config.risk.max_drawdown_limit,
                allow_shorting=config.risk.allow_shorting,
            )
            position_sizer = self._resolve_position_sizer(config)

            # Resolve decision provider
            active_provider = self.decision_provider
            decision_freq = "on_signal"
            decision_freq_n = 5
            if config.jev and config.jev.enabled:
                decision_freq = config.jev.decision_frequency
                decision_freq_n = config.jev.frequency_n
                if active_provider is None:
                    from backend.app.ai.jev_client import JevClient
                    from backend.app.ai.jev_decision import JevDecisionProvider
                    from backend.app.core.config import settings

                    j_client = JevClient(
                        api_key=settings.jev_api_key,
                        model=config.jev.model,
                        api_url=settings.jev_api_url,
                        timeout_seconds=config.jev.timeout_seconds,
                    )
                    active_provider = JevDecisionProvider(
                        client=j_client,
                        min_confidence=config.jev.min_confidence,
                        cache_enabled=config.jev.cache_enabled,
                        model=config.jev.model,
                    )

            engine = BacktestEngine(
                symbol=primary_symbol,
                initial_capital=config.portfolio.initial_capital,
                commission_fixed=config.execution.commission_fixed,
                commission_percent=config.execution.commission_percent,
                slippage_bps=config.execution.slippage_bps,
                max_position_pct=config.risk.max_position_pct,
                max_drawdown_limit=config.risk.max_drawdown_limit,
                allow_shorting=config.risk.allow_shorting,
                position_sizer=position_sizer,
                risk_manager=risk_manager,
                broker=broker,
                decision_provider=active_provider,
                decision_frequency=decision_freq,
                decision_frequency_n=decision_freq_n,
                config_hash=config.get_hash(),
            )

            bt_result = engine.run(data=raw_data, strategy=strategy)
            metrics_dict = (
                bt_result.metrics.model_dump()
                if hasattr(bt_result.metrics, "model_dump")
                else bt_result.metrics.dict()
            )
            equity_curve = bt_result.equity_curve
            trade_records = bt_result.trades
            ai_decision_stats = getattr(engine, "ai_decision_stats", None) if active_provider else None

        # 6. Compute Drawdown Curve
        drawdown_curve: List[Dict[str, Any]] = []
        hwm = 0.0
        for pt in equity_curve:
            eq = float(pt.get("total_equity", pt.get("equity", 0.0)))
            if eq > hwm:
                hwm = eq
            dd_pct = (hwm - eq) / hwm if hwm > 0 else 0.0
            drawdown_curve.append({
                "timestamp": pt["timestamp"],
                "equity": round(eq, 2),
                "total_equity": round(eq, 2),
                "high_watermark": round(hwm, 2),
                "drawdown_pct": round(dd_pct, 4),
            })

        t_end = time.perf_counter()
        runtime_ms = round((t_end - t_start) * 1000, 2)

        # 7. Execution Statistics
        execution_stats = {
            "total_bars": len(df_eval),
            "runtime_ms": runtime_ms,
            "trade_count": len(trade_records),
            "initial_capital": config.portfolio.initial_capital,
            "commission_fixed": config.execution.commission_fixed,
            "commission_percent": config.execution.commission_percent,
            "slippage_bps": config.execution.slippage_bps,
            "seed": config.seed,
        }

        # 8. Deterministic experiment ID & configuration hash
        config_hash = config.get_hash()
        experiment_id = f"exp_{config_hash[:12]}"

        result = ExperimentResult(
            experiment_id=experiment_id,
            configuration_hash=config_hash,
            config=config.to_dict(),
            dataset_metadata=dataset_meta_dict,
            strategy_info={"name": config.strategy.name, "parameters": config.strategy.parameters},
            metrics=metrics_dict,
            trade_records=trade_records,
            equity_curve=equity_curve,
            drawdown_curve=drawdown_curve,
            execution_statistics=execution_stats,
            walk_forward_results=walk_forward_payload,
            ai_decision_stats=ai_decision_stats,
            classification_metrics=classification_metrics_dict,
            feature_importance=feature_importance_dict,
            warnings=warnings,
            created_at=created_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

        # 9. Persist result
        if self.storage is not None:
            self.storage.save_experiment(result)

        return result


def compare_strategy_providers(
    experiments: List[ExperimentResult],
) -> Dict[str, Any]:
    """Builds unified comparative summary across Traditional, ML, and Jev experiments."""
    comparisons = []
    for exp in experiments:
        cfg = exp.config
        strat_name = cfg.get("strategy", {}).get("name", "Unknown")
        is_jev = bool(cfg.get("jev") and cfg.get("jev", {}).get("enabled"))
        is_ml = strat_name == "MLStrategy" or bool(cfg.get("ml") and cfg.get("ml", {}).get("enabled"))

        if is_jev:
            provider = "typesafe_jev"
            cat = "jev_assisted"
        elif is_ml:
            provider = "xgboost"
            cat = "machine_learning"
        else:
            provider = "rule_based"
            cat = "traditional"

        entry = {
            "experiment_id": exp.experiment_id,
            "strategy_name": strat_name,
            "category": cat,
            "provider": provider,
            "trading_metrics": {
                "total_return_pct": exp.metrics.get("total_return_pct"),
                "cagr": exp.metrics.get("cagr"),
                "sharpe_ratio": exp.metrics.get("sharpe_ratio"),
                "sortino_ratio": exp.metrics.get("sortino_ratio"),
                "max_drawdown_pct": exp.metrics.get("max_drawdown_pct"),
                "win_rate": exp.metrics.get("win_rate"),
                "profit_factor": exp.metrics.get("profit_factor"),
                "total_trades": exp.metrics.get("total_trades"),
            },
            "classification_metrics": exp.classification_metrics,
            "ai_decision_stats": exp.ai_decision_stats,
            "feature_importance": exp.feature_importance,
        }
        comparisons.append(entry)

    return {
        "count": len(comparisons),
        "comparisons": comparisons,
    }
