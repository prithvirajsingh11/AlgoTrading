"""Unit and integration tests for Real-Time Market Data Provider and Adapters."""

import pytest
import asyncio
from datetime import datetime, timezone

from backend.app.data.loader import OHLCVBar, MarketSnapshot
from backend.app.paper.realtime import (
    ConnectionState,
    ProviderStatus,
    InMemoryStreamingAdapter,
    GenericWebSocketAdapter,
    RealTimeMarketDataProvider,
)


def test_in_memory_adapter_lifecycle():
    async def _test():
        adapter = InMemoryStreamingAdapter(symbols=["AAPL", "MSFT"], tick_interval_seconds=0.01)
        assert adapter.status.state == ConnectionState.DISCONNECTED
        assert not adapter.status.connected

        await adapter.connect()
        assert adapter.status.state == ConnectionState.CONNECTED
        assert adapter.status.connected
        assert "AAPL" in adapter.status.subscribed_symbols
        assert "MSFT" in adapter.status.subscribed_symbols

        # Subscribe & unsubscribe
        await adapter.subscribe(["GOOGL"])
        assert "GOOGL" in adapter.symbols
        await adapter.unsubscribe(["MSFT"])
        assert "MSFT" not in adapter.symbols

        await adapter.disconnect()
        assert adapter.status.state == ConnectionState.DISCONNECTED
        assert not adapter.status.connected

    asyncio.run(_test())


def test_in_memory_adapter_stream_and_quote():
    async def _test():
        adapter = InMemoryStreamingAdapter(
            symbols=["AAPL"],
            tick_interval_seconds=0.01,
            quote_only=True,
        )
        await adapter.connect()

        count = 0
        async for snap in adapter.stream():
            count += 1
            assert "AAPL" in snap.bars
            bar = snap.bars["AAPL"]
            assert bar.bid is not None
            assert bar.ask is not None
            assert bar.mid is not None
            assert bar.mid == pytest.approx((bar.bid + bar.ask) / 2.0, rel=1e-3)
            if count >= 3:
                break

        await adapter.disconnect()

    asyncio.run(_test())


def test_generic_websocket_adapter_normalization():
    adapter = GenericWebSocketAdapter(api_url="wss://mock.feed/v1", symbols=["AAPL"])

    # Normalization of standard OHLCV
    raw_ohlc = {
        "timestamp": 1700000000,
        "symbol": "AAPL",
        "open": 150.0,
        "high": 155.0,
        "low": 149.0,
        "close": 153.5,
        "volume": 12000,
    }
    snap = adapter.normalize_message(raw_ohlc)
    assert snap is not None
    assert "AAPL" in snap.bars
    bar = snap.bars["AAPL"]
    assert bar.close == 153.5
    assert bar.open == 150.0
    assert bar.volume == 12000

    # Normalization with quote-only (bid/ask mid fallback)
    raw_quote = {
        "t": 1700000000000,  # milliseconds
        "s": "MSFT",
        "bid": 310.0,
        "ask": 312.0,
    }
    snap2 = adapter.normalize_message(raw_quote)
    assert snap2 is not None
    assert "MSFT" in snap2.bars
    bar2 = snap2.bars["MSFT"]
    assert bar2.close == 311.0
    assert bar2.bid == 310.0
    assert bar2.ask == 312.0
    assert bar2.open is None  # Does not fabricate OHLC

    # Malformed payload handled safely without exceptions
    assert adapter.normalize_message({}) is None
    assert adapter.normalize_message({"invalid": "garbage"}) is None


def test_realtime_provider_lifecycle_and_buffer():
    async def _test():
        adapter = InMemoryStreamingAdapter(symbols=["AAPL"], tick_interval_seconds=0.01)
        provider = RealTimeMarketDataProvider(
            adapter=adapter,
            symbols=["AAPL"],
            max_buffer_size=5,
        )

        await provider.connect()
        assert provider.status.connected

        # Stream 6 snapshots to verify bounded buffer pop
        count = 0
        async for snap in provider.stream():
            count += 1
            if count >= 6:
                break

        assert provider.get_total_bars() >= 6
        assert len(provider._history_snapshots) <= 5
        assert provider.latest_snapshot() is not None

        # Slice extraction without lookahead
        slice_df = provider.get_slice(up_to_index=2)
        assert len(slice_df) <= 3

        await provider.disconnect()
        assert not provider.status.connected

    asyncio.run(_test())


def test_realtime_provider_reconnect_backoff():
    async def _test():
        class FailingAdapter(InMemoryStreamingAdapter):
            def __init__(self):
                super().__init__(symbols=["AAPL"])
                self.attempts = 0

            async def connect(self):
                self.attempts += 1
                if self.attempts < 3:
                    raise ConnectionError("Mock connection failure")
                await super().connect()

        failing_adapter = FailingAdapter()
        provider = RealTimeMarketDataProvider(
            adapter=failing_adapter,
            symbols=["AAPL"],
            max_reconnect_attempts=4,
            reconnect_backoff_factor=1.1,
        )

        await provider.connect()
        assert provider.status.connected
        assert failing_adapter.attempts == 3
        assert provider.status.reconnect_count == 2
        await provider.disconnect()

    asyncio.run(_test())
