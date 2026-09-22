"""Tests verifying bounded memory structures across real-time streaming components.

Guarantees:
1. StreamingFeatureEngine buffers do not exceed max_buffer_size.
2. PaperTradingService.recent_events is capped (does not grow unbounded).
3. BarBuilder incomplete bars are bounded to active symbols count.
"""

from collections import deque
from datetime import datetime, timezone, timedelta
import tempfile
from pathlib import Path
import pytest

from backend.app.paper.streaming_features import StreamingFeatureEngine
from backend.app.data.loader import OHLCVBar, MarketSnapshot
from backend.app.paper.bar_builder import BarBuilder
from backend.app.paper.realtime import MarketTick
from backend.app.paper.service import PaperTradingService
from backend.app.paper.storage import SQLitePaperStorage
from backend.app.paper.events import MarketEvent


def test_streaming_feature_engine_bounded_buffers():
    """Verifies that StreamingFeatureEngine ring buffers never exceed max_buffer_size."""
    max_buf = 50
    engine = StreamingFeatureEngine(symbols=["AAPL"], max_buffer_size=max_buf)
    
    base_time = datetime(2026, 9, 22, 10, 0, 0, tzinfo=timezone.utc)
    for i in range(200):
        t = base_time + timedelta(seconds=i)
        bar = OHLCVBar(
            timestamp=t,
            open=150.0,
            high=152.0,
            low=149.0,
            close=150.0 + (i * 0.1),
            volume=1000.0,
            symbol="AAPL",
        )
        engine.update_bar(bar)
        
    buf = engine._buffers["AAPL"]
    assert len(buf) == engine.max_buffer_size
    assert len(buf) <= max(max_buf, engine.feature_engineer.warmup_bars + 20)


def test_paper_trading_service_recent_events_bounded():
    """Verifies that PaperTradingService.recent_events never grows unbounded."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = SQLitePaperStorage(str(Path(tmp_dir) / "test_mem_events.db"))
        svc = PaperTradingService(storage=storage)

        sid = "paper_mem_test_session"
        svc.recent_events[sid] = []

        base_time = datetime(2026, 9, 22, 10, 0, 0, tzinfo=timezone.utc)
        for i in range(1200):
            evt = MarketEvent(
                timestamp=(base_time + timedelta(seconds=i)).isoformat(),
                event_type="MARKET_BAR",
                session_id=sid,
                symbol="AAPL",
                open=150.0,
                high=152.0,
                low=149.0,
                close=151.0,
                volume=1000.0,
                bar_index=i,
                total_bars=2000,
            )
            svc._record_event(sid, evt)

        # Capped at 500 items max
        assert len(svc.recent_events[sid]) <= 500


def test_bar_builder_memory_bounds():
    """Verifies that BarBuilder only stores ongoing bars for configured symbols."""
    symbols = ["AAPL", "MSFT"]
    builder = BarBuilder(interval="1m", symbols=symbols)

    base_time = datetime(2026, 9, 22, 10, 0, 0, tzinfo=timezone.utc)
    for i in range(300):
        t = base_time + timedelta(seconds=i)
        builder.add_tick(MarketTick(symbol="AAPL", timestamp=t, price=150.0, received_at=t))
        builder.add_tick(MarketTick(symbol="MSFT", timestamp=t, price=250.0, received_at=t))

    assert len(builder._current_bars) <= len(symbols)
