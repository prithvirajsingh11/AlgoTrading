"""Opt-in live smoke test for TypeSafe SystemOne Jev API.

Only runs when explicit live credentials and opt-in flag are set:
  JEV_API_KEY=<valid_key>
  JEV_SMOKE_TEST=true
Normal automated tests and CI bypass this test completely.
"""

import os
import pytest
from backend.app.ai.jev_client import JevClient
from backend.app.ai.jev_schema import JevDecisionType

API_KEY = os.getenv("JEV_API_KEY")
SMOKE_ENABLED = os.getenv("JEV_SMOKE_TEST", "").lower() in ("true", "1", "yes")


@pytest.mark.skipif(
    not (API_KEY and SMOKE_ENABLED),
    reason="Opt-in live test requires JEV_API_KEY environment variable and JEV_SMOKE_TEST=true",
)
def test_live_typesafe_systemone_smoke():
    """Optional live smoke test executing one real request against TypeSafe SystemOne."""
    client = JevClient(
        api_key=API_KEY,
        model=os.getenv("JEV_MODEL", "jev-latest"),
        timeout_seconds=10.0,
    )

    state = {
        "symbol": "AAPL",
        "timestamp": "2026-09-21T12:00:00Z",
        "price": 225.50,
        "recent_return": 0.015,
        "rsi_14": 58.2,
        "macd": {"macd": 1.25, "signal": 0.95, "histogram": 0.30},
        "portfolio": {"cash": 100000.0, "equity": 100000.0, "exposure_pct": 0.0},
    }

    decision = client.evaluate_state(state=state, timestamp="2026-09-21T12:00:00Z")

    assert decision.decision in (
        JevDecisionType.BUY,
        JevDecisionType.SELL,
        JevDecisionType.HOLD,
        JevDecisionType.NO_ACTION,
    )
    assert decision.confidence >= 0.0
    assert "BUY" in decision.probabilities
    assert "SELL" in decision.probabilities
    assert "HOLD" in decision.probabilities
    assert decision.source in ("LIVE_JEV", "FALLBACK")
