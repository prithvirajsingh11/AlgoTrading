"""Security and Credential Hygiene Tests for Real-Time Market Data and Paper Trading."""

import pytest
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.paper.realtime import (
    ProviderStatus,
    GenericWebSocketAdapter,
    AlpacaMarketDataAdapter,
    ConnectionState,
)

client = TestClient(app)


def test_provider_status_credential_hygiene():
    # Simulate adapter with credentials
    adapter = GenericWebSocketAdapter(
        api_url="wss://secret.feed/stream",
        api_key="SUPER_SECRET_API_KEY_12345",
        api_secret="SUPER_SECRET_API_SECRET_67890",
        symbols=["AAPL"],
    )

    status = adapter.get_status()
    d = status.to_dict()

    # Verify no raw credentials leaked into dictionary serialization
    for key, val in d.items():
        assert "SECRET" not in str(key).upper()
        assert "12345" not in str(val)
        assert "67890" not in str(val)


def test_alpaca_credential_hygiene():
    adapter = AlpacaMarketDataAdapter(
        api_key="ALPACA_SECRET_KEY_ID",
        secret_key="ALPACA_SUPER_SECRET_VALUE",
    )
    status_dict = adapter.status.to_dict()
    assert status_dict["api_key_configured"] is True
    # Verify exact secret values never appear
    assert "ALPACA_SECRET_KEY_ID" not in str(status_dict)
    assert "ALPACA_SUPER_SECRET_VALUE" not in str(status_dict)
    assert "secret_key" not in status_dict


def test_market_api_credential_hygiene():
    # 1. /api/v1/market/providers
    res = client.get("/api/v1/market/providers")
    assert res.status_code == 200
    text_data = res.text
    assert "SUPER_SECRET" not in text_data

    # 2. /api/v1/market/status
    res_status = client.get("/api/v1/market/status")
    assert res_status.status_code == 200
    text_status = res_status.text
    assert "secret" not in text_status.lower()


def test_paper_session_and_export_credential_hygiene():
    # Create real-time session
    req_body = {
        "dataset_id": "AAPL",
        "symbols": ["AAPL"],
        "strategy": "TimeSeriesMomentum",
        "mode": "REAL_TIME",
        "data_provider": "LIVE_PROVIDER",
        "live_provider": "alpaca",
        "initial_capital": 50_000.0,
    }
    res = client.post("/api/v1/paper/sessions", json={**req_body, "strategy_params": {}})
    assert res.status_code == 200
    sess = res.json()
    sid = sess["session_id"]

    # Session GET
    get_res = client.get(f"/api/v1/paper/sessions/{sid}")
    assert get_res.status_code == 200
    sess_text = get_res.text
    assert "secret" not in sess_text.lower()

    # Session export
    export_res = client.get(f"/api/v1/paper/sessions/{sid}/export")
    assert export_res.status_code == 200
    export_text = export_res.text
    assert "secret" not in export_text.lower()
