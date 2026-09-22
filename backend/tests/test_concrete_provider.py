"""Unit tests for concrete AlpacaMarketDataAdapter."""

import pytest
from datetime import datetime, timezone
from backend.app.paper.realtime import (
    AlpacaMarketDataAdapter,
    ConnectionState,
    MarketTick,
)


def test_alpaca_unconfigured_behavior():
    """Unconfigured credentials must set NOT_CONFIGURED state without exceptions."""
    adapter = AlpacaMarketDataAdapter(
        api_key=None,
        secret_key=None,
        feed="iex",
    )
    assert adapter.status.state == ConnectionState.NOT_CONFIGURED.value
    assert adapter.status.api_key_configured is False
    assert adapter.status.connected is False

    # Status dict must never contain secret keys
    d = adapter.status.to_dict()
    assert d["state"] == "NOT_CONFIGURED"
    assert d["api_key_configured"] is False
    assert "secret" not in str(d).lower()
    assert "key" not in d or d["key"] is None or d["api_key_configured"] is False


def test_alpaca_configured_initialization():
    adapter = AlpacaMarketDataAdapter(
        api_key="TEST_KEY_ID_123",
        secret_key="TEST_SECRET_456",
        feed="iex",
    )
    assert adapter.status.api_key_configured is True
    assert adapter.status.state == ConnectionState.DISCONNECTED.value

    # Verify credentials never leaked in status
    st = adapter.status.to_dict()
    assert "TEST_KEY_ID_123" not in str(st)
    assert "TEST_SECRET_456" not in str(st)


def test_alpaca_auth_payload():
    adapter = AlpacaMarketDataAdapter(
        api_key="TEST_KEY_1",
        secret_key="TEST_SECRET_2",
    )
    auth_msg = adapter.get_auth_payload()
    assert auth_msg["action"] == "auth"
    assert auth_msg["key"] == "TEST_KEY_1"
    assert auth_msg["secret"] == "TEST_SECRET_2"


def test_alpaca_subscribe_payload():
    adapter = AlpacaMarketDataAdapter(
        api_key="KEY",
        secret_key="SEC",
    )
    sub_msg = adapter.get_subscribe_payload(["AAPL", "MSFT"])
    assert sub_msg["action"] == "subscribe"
    assert "AAPL" in sub_msg["quotes"]
    assert "MSFT" in sub_msg["quotes"]
    assert "AAPL" in sub_msg["trades"]
    assert "AAPL" in sub_msg["bars"]


def test_alpaca_trade_normalization():
    adapter = AlpacaMarketDataAdapter(api_key="K", secret_key="S")
    raw_trade = {
        "T": "t",
        "S": "AAPL",
        "p": 175.50,
        "s": 100,
        "t": "2026-03-15T14:30:00.123456Z",
    }
    tick = adapter.normalize_message(raw_trade)
    assert tick is not None
    assert isinstance(tick, MarketTick)
    assert tick.symbol == "AAPL"
    assert tick.price == 175.50
    assert tick.size == 100
    assert tick.bid is None
    assert tick.timestamp.year == 2026


def test_alpaca_quote_normalization():
    adapter = AlpacaMarketDataAdapter(api_key="K", secret_key="S")
    raw_quote = {
        "T": "q",
        "S": "MSFT",
        "bp": 420.10,
        "bs": 10,
        "ap": 420.20,
        "as": 20,
        "t": "2026-03-15T14:30:01.000000Z",
    }
    tick = adapter.normalize_message(raw_quote)
    assert tick is not None
    assert tick.symbol == "MSFT"
    assert tick.bid == 420.10
    assert tick.ask == 420.20
    assert tick.price == 420.15  # mid price
    assert tick.size == 20


def test_alpaca_bar_normalization():
    adapter = AlpacaMarketDataAdapter(api_key="K", secret_key="S")
    raw_bar = {
        "T": "b",
        "S": "NVDA",
        "o": 120.0,
        "h": 125.0,
        "l": 119.5,
        "c": 124.0,
        "v": 50000,
        "t": "2026-03-15T14:31:00Z",
    }
    tick = adapter.normalize_message(raw_bar)
    assert tick is not None
    assert tick.symbol == "NVDA"
    assert tick.price == 124.0
    assert tick.size == 50000


def test_alpaca_unrecognized_message():
    adapter = AlpacaMarketDataAdapter(api_key="K", secret_key="S")
    # System / subscription confirmation message should return None without error
    sys_msg = [{"T": "subscription", "quotes": ["AAPL"]}]
    ticks = adapter.parse_raw_payload(sys_msg)
    assert len(ticks) == 0
