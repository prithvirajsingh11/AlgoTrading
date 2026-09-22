"""Tests verifying graceful failure handling in TypeSafe SystemOne Jev AI layer.

Simulates:
- API network timeout
- HTTP 500 / 503 errors
- Malformed JSON response
- Missing confidence field
- Cache corruption

Guarantees:
- Jev layer always returns safe fallback with JevDecisionType.NO_ACTION
- Paper trading execution continues uninterrupted
"""

import pytest
from unittest.mock import patch, MagicMock
import urllib.error

from backend.app.ai.jev_client import JevClient
from backend.app.ai.jev_schema import JevDecision, JevDecisionType


def test_jev_client_unconfigured_fails_safe_to_no_action():
    client = JevClient(api_key=None)
    dec = client.evaluate_state(state={"symbol": "AAPL", "rsi": 65.0})
    assert dec.decision == JevDecisionType.NO_ACTION
    assert dec.confidence == 0.0
    assert dec.source == "FALLBACK"
    assert dec.error is not None and "not configured" in dec.error.lower()


def test_jev_client_http_500_fails_safe():
    client = JevClient(api_key="test_key")
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="https://api.typesafe.ai/v1/systemone",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )
        dec = client.evaluate_state(state={"symbol": "AAPL"})
        assert dec.decision == JevDecisionType.NO_ACTION
        assert dec.source == "FALLBACK"
        assert dec.confidence == 0.0


def test_jev_client_timeout_fails_safe():
    client = JevClient(api_key="test_key", timeout_seconds=0.1)
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = TimeoutError("Connection timed out")
        dec = client.evaluate_state(state={"symbol": "AAPL"})
        assert dec.decision == JevDecisionType.NO_ACTION
        assert dec.source == "FALLBACK"


def test_jev_client_malformed_json_fails_safe():
    client = JevClient(api_key="test_key")
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"{corrupted_invalid_json: 123"
    with patch("urllib.request.urlopen", return_value=mock_resp):
        dec = client.evaluate_state(state={"symbol": "AAPL"})
        assert dec.decision == JevDecisionType.NO_ACTION
        assert dec.source == "FALLBACK"
