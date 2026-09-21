"""Tests for JevDecisionProvider, confidence policy, DecisionCache, and MockDecisionProvider."""

from unittest.mock import MagicMock
from backend.app.ai.jev_schema import JevDecision, JevDecisionType
from backend.app.ai.jev_client import JevClient
from backend.app.ai.jev_decision import (
    JevDecisionProvider,
    DecisionCache,
    MockDecisionProvider,
)


def test_confidence_threshold_retains_high_confidence():
    """High confidence actionable decision passes threshold unchanged."""
    client = MagicMock(spec=JevClient)
    client.evaluate_state.return_value = JevDecision(
        decision=JevDecisionType.BUY,
        confidence=0.75,
        probabilities={"BUY": 0.75, "SELL": 0.10, "HOLD": 0.15},
        model="jev-latest",
        timestamp="2023-01-10",
        source="LIVE_JEV",
    )

    provider = JevDecisionProvider(client=client, min_confidence=0.60, cache_enabled=False)
    dec = provider.evaluate({"symbol": "AAPL", "price": 100.0})

    assert dec.decision == JevDecisionType.BUY
    assert dec.confidence == 0.75


def test_confidence_threshold_demotes_low_confidence_to_hold():
    """Actionable decision below min_confidence must be demoted to HOLD."""
    client = MagicMock(spec=JevClient)
    client.evaluate_state.return_value = JevDecision(
        decision=JevDecisionType.BUY,
        confidence=0.45,  # Below 0.60
        probabilities={"BUY": 0.45, "SELL": 0.30, "HOLD": 0.25},
        model="jev-latest",
        timestamp="2023-01-10",
        source="LIVE_JEV",
    )

    provider = JevDecisionProvider(client=client, min_confidence=0.60, cache_enabled=False)
    dec = provider.evaluate({"symbol": "AAPL", "price": 100.0})

    assert dec.decision == JevDecisionType.HOLD
    assert dec.confidence == 0.45
    assert "confidence_filter" in dec.request_metadata


def test_decision_cache_hit_and_reproducibility():
    """Verify DecisionCache serves subsequent evaluations as CACHED_JEV."""
    client = MagicMock(spec=JevClient)
    client.evaluate_state.return_value = JevDecision(
        decision=JevDecisionType.BUY,
        confidence=0.85,
        probabilities={"BUY": 0.85, "SELL": 0.05, "HOLD": 0.10},
        model="jev-latest",
        timestamp="2023-01-10",
        source="LIVE_JEV",
    )

    cache = DecisionCache()
    provider = JevDecisionProvider(client=client, min_confidence=0.60, cache=cache, cache_enabled=True)

    context = {"symbol": "AAPL", "timestamp": "2023-01-10", "price": 150.0}

    # First call: hits live client
    dec1 = provider.evaluate(context, config_hash="hash_1")
    assert dec1.source == "LIVE_JEV"
    assert client.evaluate_state.call_count == 1
    assert len(cache) == 1

    # Second call: served from cache
    dec2 = provider.evaluate(context, config_hash="hash_1")
    assert dec2.source == "CACHED_JEV"
    assert dec2.decision == dec1.decision
    assert dec2.confidence == dec1.confidence
    # Live client not called again
    assert client.evaluate_state.call_count == 1

    # Third call with different config hash: cache miss, hits client
    dec3 = provider.evaluate(context, config_hash="hash_2")
    assert dec3.source == "LIVE_JEV"
    assert client.evaluate_state.call_count == 2
    assert len(cache) == 2


def test_mock_decision_provider():
    """Verify MockDecisionProvider provides deterministic responses and error states."""
    mock_prov = MockDecisionProvider(
        default_decision=JevDecisionType.SELL,
        confidence=0.92,
        latency_ms=8.5,
    )

    dec = mock_prov.evaluate({"symbol": "TSLA", "timestamp": "2023-02-01"})
    assert dec.decision == JevDecisionType.SELL
    assert dec.confidence == 0.92
    assert dec.source == "MOCK"
    assert mock_prov.call_count == 1

    # Error simulation
    mock_fail = MockDecisionProvider(fail_with_error="Simulated network failure")
    dec_err = mock_fail.evaluate({"symbol": "TSLA"})
    assert dec_err.decision == JevDecisionType.NO_ACTION
    assert dec_err.error == "Simulated network failure"
