"""Unit tests for BarBuilder tick-to-bar aggregation."""

import pytest
from datetime import datetime, timezone, timedelta
from backend.app.paper.bar_builder import BarBuilder, IncompleteBar
from backend.app.paper.realtime import MarketTick


def test_bar_builder_initialization():
    bb = BarBuilder(interval="1m")
    assert bb.interval == "1m"
    assert bb.interval_seconds == 60


def test_bar_builder_unsupported_interval():
    with pytest.raises(ValueError, match="Unsupported interval"):
        BarBuilder(interval="3m")


def test_bar_builder_bucket_alignment():
    bb = BarBuilder(interval="1m")
    dt = datetime(2026, 3, 15, 14, 23, 45, 123456, tzinfo=timezone.utc)
    aligned = bb._align_timestamp(dt)
    assert aligned == datetime(2026, 3, 15, 14, 23, 0, tzinfo=timezone.utc)

    bb5 = BarBuilder(interval="5m")
    aligned5 = bb5._align_timestamp(dt)
    assert aligned5 == datetime(2026, 3, 15, 14, 20, 0, tzinfo=timezone.utc)


def test_bar_builder_tick_aggregation():
    bb = BarBuilder(interval="1m")
    t0 = datetime(2026, 3, 15, 10, 0, 5, tzinfo=timezone.utc)

    # First tick opens the bar
    tick1 = MarketTick(
        symbol="AAPL",
        timestamp=t0,
        price=150.0,
        size=10.0,
        bid=149.95,
        ask=150.05,
    )
    closed = bb.on_tick(tick1)
    assert closed is None  # bar is not closed yet

    incomplete = bb.get_incomplete_bar("AAPL")
    assert incomplete is not None
    assert incomplete.open == 150.0
    assert incomplete.high == 150.0
    assert incomplete.low == 150.0
    assert incomplete.close == 150.0
    assert incomplete.volume == 10.0
    assert incomplete.tick_count == 1

    # Second tick in same minute - updates high and volume
    tick2 = MarketTick(
        symbol="AAPL",
        timestamp=t0 + timedelta(seconds=10),
        price=152.0,
        size=5.0,
    )
    closed = bb.on_tick(tick2)
    assert closed is None

    incomplete = bb.get_incomplete_bar("AAPL")
    assert incomplete.high == 152.0
    assert incomplete.low == 150.0
    assert incomplete.close == 152.0
    assert incomplete.volume == 15.0
    assert incomplete.tick_count == 2

    # Third tick in same minute - updates low
    tick3 = MarketTick(
        symbol="AAPL",
        timestamp=t0 + timedelta(seconds=20),
        price=149.0,
        size=20.0,
    )
    closed = bb.on_tick(tick3)
    assert closed is None

    incomplete = bb.get_incomplete_bar("AAPL")
    assert incomplete.high == 152.0
    assert incomplete.low == 149.0
    assert incomplete.close == 149.0
    assert incomplete.volume == 35.0
    assert incomplete.tick_count == 3


def test_bar_builder_rollover_finalization():
    bb = BarBuilder(interval="1m")
    t0 = datetime(2026, 3, 15, 10, 0, 10, tzinfo=timezone.utc)

    bb.on_tick(MarketTick("AAPL", t0, 150.0, 10.0))
    bb.on_tick(MarketTick("AAPL", t0 + timedelta(seconds=15), 155.0, 5.0))

    # Tick in next minute bucket (10:01:05) closes previous 10:00:00 bar
    t1 = datetime(2026, 3, 15, 10, 1, 5, tzinfo=timezone.utc)
    closed_bar = bb.on_tick(MarketTick("AAPL", t1, 156.0, 8.0))

    assert closed_bar is not None
    assert closed_bar.symbol == "AAPL"
    assert closed_bar.timestamp == datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
    assert closed_bar.open == 150.0
    assert closed_bar.high == 155.0
    assert closed_bar.low == 150.0
    assert closed_bar.close == 155.0
    assert closed_bar.volume == 15.0

    # New incomplete bar started for 10:01:00
    new_inc = bb.get_incomplete_bar("AAPL")
    assert new_inc is not None
    assert new_inc.bucket_start == datetime(2026, 3, 15, 10, 1, 0, tzinfo=timezone.utc)
    assert new_inc.open == 156.0
    assert new_inc.close == 156.0
    assert new_inc.volume == 8.0


def test_bar_builder_manual_finalize():
    bb = BarBuilder(interval="1m")
    t0 = datetime(2026, 3, 15, 10, 0, 10, tzinfo=timezone.utc)
    bb.on_tick(MarketTick("MSFT", t0, 300.0, 50.0))

    finalized = bb.finalize_bar("MSFT")
    assert finalized is not None
    assert finalized.symbol == "MSFT"
    assert finalized.close == 300.0
    assert bb.get_incomplete_bar("MSFT") is None

    # Finalizing non-existent returns None
    assert bb.finalize_bar("UNKNOWN") is None
