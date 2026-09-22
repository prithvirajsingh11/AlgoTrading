"""Tests verifying unambiguous decision attribution across all order and trade executions.

Sources:
- RULE_BASED: Traditional quantitative rules (momentum, mean reversion, moving averages).
- XGBOOST: Machine learning directional inference (with model version, prediction, probability).
- JEV: AI decision layer validation (with model, decision, confidence, live/cache source).
- JEV_ASSISTED: Hybrid strategy where ML signal is filtered or sized by Jev AI.
"""

from datetime import datetime, timezone
import pytest
from backend.app.paper.orders import PaperOrderRecord, PaperOrderManager
from backend.app.backtesting.orders import OrderSide, OrderType, SignalEvent, SignalType
from backend.app.paper.events import StrategySignalEvent, MLPredictionEvent, JevDecisionEvent


def test_paper_order_record_decision_lineage():
    mgr = PaperOrderManager(session_id="paper_test_attribution")

    # 1. Rule based order
    o_rule = mgr.create_order(
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=10,
        timestamp=datetime.now(timezone.utc),
        strategy_name="TimeSeriesMomentum",
        decision_source="RULE_BASED",
    )
    assert o_rule.decision_source == "RULE_BASED"
    assert o_rule.model_version is None
    assert o_rule.to_dict()["decision_source"] == "RULE_BASED"

    # 2. XGBoost order
    o_ml = mgr.create_order(
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=15,
        timestamp=datetime.now(timezone.utc),
        strategy_name="MLStrategy",
        decision_source="XGBOOST",
        model_version="xgb_v2.1",
    )
    assert o_ml.decision_source == "XGBOOST"
    assert o_ml.model_version == "xgb_v2.1"
    d_ml = o_ml.to_dict()
    assert d_ml["decision_source"] == "XGBOOST"
    assert d_ml["model_version"] == "xgb_v2.1"

    # 3. Jev order
    o_jev = mgr.create_order(
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=5,
        timestamp=datetime.now(timezone.utc),
        strategy_name="MovingAverageCross",
        decision_source="JEV",
        jev_mode="LIVE_JEV",
    )
    assert o_jev.decision_source == "JEV"
    assert o_jev.jev_mode == "LIVE_JEV"
    d_jev = o_jev.to_dict()
    assert d_jev["decision_source"] == "JEV"
    assert d_jev["jev_mode"] == "LIVE_JEV"

    # 4. Jev-assisted order
    o_assist = mgr.create_order(
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=20,
        timestamp=datetime.now(timezone.utc),
        strategy_name="MLStrategy",
        decision_source="JEV_ASSISTED",
        model_version="xgb_v2.1",
        jev_mode="CACHED_JEV",
    )
    assert o_assist.decision_source == "JEV_ASSISTED"
    assert o_assist.model_version == "xgb_v2.1"
    assert o_assist.jev_mode == "CACHED_JEV"


def test_decision_event_payloads():
    ts = datetime.now(timezone.utc).isoformat()

    # ML Prediction Event
    ml_evt = MLPredictionEvent(
        timestamp=ts,
        event_type="ML_PREDICTION",
        session_id="paper_ml_01",
        symbol="AAPL",
        model_version="xgb_v1.0",
        prediction=0.68,
        features_used=12,
    )
    d_ml = ml_evt.to_dict()
    assert d_ml["model_version"] == "xgb_v1.0"
    assert d_ml["prediction"] == 0.68
    assert d_ml["features_used"] == 12

    # Jev Decision Event
    jev_evt = JevDecisionEvent(
        timestamp=ts,
        event_type="JEV_DECISION",
        session_id="paper_jev_01",
        symbol="AAPL",
        decision="BUY",
        confidence=0.85,
        mode="LIVE_JEV",
        rationale="Strong upward momentum with low regime volatility",
    )
    d_jev = jev_evt.to_dict()
    assert d_jev["decision"] == "BUY"
    assert d_jev["confidence"] == 0.85
    assert d_jev["mode"] == "LIVE_JEV"
    assert "Strong upward momentum" in d_jev["rationale"]
