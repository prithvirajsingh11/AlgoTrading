"""Tests for TypeSafe SystemOne Jev schema, request builder, and HTTP client fail-safety."""

import json
from unittest.mock import patch, MagicMock
import urllib.error

from backend.app.ai.jev_schema import (
    JevDecision,
    JevDecisionType,
    JevDecisionRequest,
)
from backend.app.ai.jev_client import JevClient


def test_jev_request_schema():
    """Verify request conforms to TypeSafe SystemOne specification."""
    req = JevDecisionRequest.create(state='{"symbol":"AAPL","price":150.0}', model="jev-latest")
    payload = req.to_dict()

    assert payload["model"] == "jev-latest"
    assert "trading_action" in payload["questions"]
    q = payload["questions"]["trading_action"]
    assert q["type"] == "choice"
    assert "BUY" in q["criteria"]
    assert "SELL" in q["criteria"]
    assert "HOLD" in q["criteria"]


def test_jev_decision_serialization():
    """Verify JevDecision round-trip serialization and deserialization."""
    decision = JevDecision(
        decision=JevDecisionType.BUY,
        confidence=0.825,
        probabilities={"BUY": 0.825, "SELL": 0.075, "HOLD": 0.100},
        model="jev-latest",
        timestamp="2023-01-05T00:00:00",
        request_metadata={"test": 1},
        latency_ms=145.2,
        context_hash="abc123hash",
        source="LIVE_JEV",
    )
    d_dict = decision.to_dict()
    assert d_dict["decision"] == "BUY"
    assert d_dict["confidence"] == 0.825
    assert d_dict["latency_ms"] == 145.2

    # Round trip JSON
    j_str = decision.to_json()
    reconstructed = JevDecision.from_json(j_str)
    assert reconstructed.decision == JevDecisionType.BUY
    assert reconstructed.confidence == 0.825
    assert reconstructed.probabilities["BUY"] == 0.825
    assert reconstructed.context_hash == "abc123hash"


def test_client_unconfigured_fails_safe():
    """Client with no API key must fail safe to NO_ACTION without making network requests."""
    client = JevClient(api_key=None)
    assert not client.is_configured

    dec = client.evaluate_state({"price": 100.0})
    assert dec.decision == JevDecisionType.NO_ACTION
    assert dec.confidence == 0.0
    assert dec.error == "JEV_API_KEY is not configured"
    assert dec.source == "FALLBACK"


def test_client_parse_valid_typesafe_response():
    """Verify client correctly parses genuine TypeSafe SystemOne choice responses."""
    client = JevClient(api_key="mock-key")

    mock_resp = MagicMock()
    mock_resp.getcode.return_value = 200
    mock_payload = {
        "questions": {
            "trading_action": {
                "type": "choice",
                "choice": "BUY",
                "confidence": 0.78,
                "probabilities": {
                    "BUY": 0.78,
                    "SELL": 0.08,
                    "HOLD": 0.14,
                },
            }
        }
    }
    mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        dec = client.evaluate_state({"price": 150.0}, timestamp="2023-01-05")
        assert dec.decision == JevDecisionType.BUY
        assert dec.confidence == 0.78
        assert dec.probabilities["BUY"] == 0.78
        assert dec.probabilities["SELL"] == 0.08
        assert dec.source == "LIVE_JEV"
        assert dec.error is None


def test_client_malformed_response_fails_safe():
    """Malformed response body must fail safe to NO_ACTION with error logged."""
    client = JevClient(api_key="mock-key")

    mock_resp = MagicMock()
    mock_resp.getcode.return_value = 200
    mock_resp.read.return_value = b'{"unexpected_format": true}'

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        dec = client.evaluate_state({"price": 150.0})
        assert dec.decision == JevDecisionType.NO_ACTION
        assert dec.confidence == 0.0
        assert "Malformed response" in (dec.error or "")


def test_client_network_timeout_fails_safe():
    """URLError / Timeout must fail safe to NO_ACTION without throwing exceptions."""
    client = JevClient(api_key="mock-key")

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection timed out")):
        dec = client.evaluate_state({"price": 150.0})
        assert dec.decision == JevDecisionType.NO_ACTION
        assert dec.confidence == 0.0
        assert "Connection timed out" in (dec.error or "")
        assert dec.source == "FALLBACK"


def test_client_http_500_fails_safe():
    """HTTP 500 error must fail safe to NO_ACTION without crashing."""
    client = JevClient(api_key="mock-key")

    http_err = urllib.error.HTTPError(
        url="https://api.typesafe.ai/v1/systemone",
        code=500,
        msg="Internal Server Error",
        hdrs={},
        fp=None,
    )

    with patch("urllib.request.urlopen", side_effect=http_err):
        dec = client.evaluate_state({"price": 150.0})
        assert dec.decision == JevDecisionType.NO_ACTION
        assert dec.confidence == 0.0
        assert "HTTPError 500" in (dec.error or "")
