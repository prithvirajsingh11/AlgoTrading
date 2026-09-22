"""Reusable tick-to-bar aggregation engine.

Enforces:
1. Configurable aggregation intervals (e.g. 1s, 1m, 5m, 15m, 1h).
2. Strict separation of LIVE TICK DATA from AGGREGATED LIVE BAR DATA.
3. Zero-lookahead guarantee: only completed bars are emitted as finalized OHLCVBar objects.
4. Robust bucket alignment using exchange timestamps.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union
import logging

from backend.app.data.loader import OHLCVBar
from backend.app.paper.realtime import MarketTick

logger = logging.getLogger("bar_builder")


ALLOWED_INTERVALS = {"1s", "5s", "10s", "15s", "30s", "1m", "5m", "15m", "30m", "1h", "4h", "1d"}


def parse_interval_seconds(interval: str) -> int:
    """Parses interval string (e.g. '1s', '1m', '5m', '15m', '1h', '1d') into seconds."""
    s = interval.strip().lower()
    if s not in ALLOWED_INTERVALS:
        raise ValueError(f"Unsupported interval: '{interval}'. Must be one of {sorted(ALLOWED_INTERVALS)}.")
    if s.endswith("s"):
        return max(1, int(s[:-1]))
    elif s.endswith("m"):
        return max(1, int(s[:-1]) * 60)
    elif s.endswith("h"):
        return max(1, int(s[:-1]) * 3600)
    elif s.endswith("d"):
        return max(1, int(s[:-1]) * 86400)
    raise ValueError(f"Unsupported interval format: '{interval}'. Use e.g. '1s', '1m', '5m', '15m', '1h'.")


@dataclass
class IncompleteBar:
    """Represents an ongoing, unfinalized bar aggregation bucket.

    STRICT INVARIANT: IncompleteBar is LIVE TICK DATA, NEVER to be passed as a finalized historical bar.
    """
    symbol: str
    interval: str
    interval_start: datetime
    interval_end: datetime
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: float = 0.0
    tick_count: int = 0
    last_tick_time: Optional[datetime] = None
    is_finalized: bool = False

    @property
    def bucket_start(self) -> datetime:
        return self.interval_start

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "interval": self.interval,
            "interval_start": self.interval_start.isoformat(),
            "interval_end": self.interval_end.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "tick_count": self.tick_count,
            "last_tick_time": self.last_tick_time.isoformat() if self.last_tick_time else None,
            "is_finalized": False,
        }


class BarBuilder:
    """Aggregates normalized MarketTick events into finalized OHLCVBar objects across configurable intervals."""

    def __init__(self, interval: str = "1m", symbols: Optional[List[str]] = None):
        self.interval = interval
        self.interval_seconds = parse_interval_seconds(interval)
        self.symbols = list(symbols) if symbols else []
        self._current_bars: Dict[str, IncompleteBar] = {}
        self._completed_bars: List[OHLCVBar] = []

    def _get_bucket_window(self, dt: datetime) -> tuple[datetime, datetime]:
        """Calculates deterministic start and end boundary for timestamp's interval bucket."""
        ts = dt.timestamp()
        bucket_sec = (int(ts) // self.interval_seconds) * self.interval_seconds
        start = datetime.fromtimestamp(bucket_sec, tz=timezone.utc)
        end = start + timedelta(seconds=self.interval_seconds)
        return start, end

    def _align_timestamp(self, dt: datetime) -> datetime:
        return self._get_bucket_window(dt)[0]

    def add_tick(self, tick: MarketTick) -> Optional[OHLCVBar]:
        """Ingests a normalized MarketTick and returns a finalized OHLCVBar if an interval has closed.

        If the tick belongs to the current ongoing bucket, updates the bucket and returns None.
        If the tick crosses into a new bucket, finalizes the previous bucket into OHLCVBar,
        starts the new bucket, and returns the completed bar.
        """
        sym = tick.symbol
        if sym not in self.symbols:
            self.symbols.append(sym)

        # Resolve price: preference last_price, then mid/bid/ask
        price = tick.last_price
        if price is None:
            if tick.bid is not None and tick.ask is not None:
                price = (tick.bid + tick.ask) / 2.0
            elif tick.bid is not None:
                price = tick.bid
            elif tick.ask is not None:
                price = tick.ask

        if price is None:
            # Tick contains no price data to aggregate
            return None

        vol = tick.volume if tick.volume is not None else 0.0
        ts = tick.exchange_timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        current = self._current_bars.get(sym)

        if current is None:
            # First tick for symbol
            start, end = self._get_bucket_window(ts)
            self._current_bars[sym] = IncompleteBar(
                symbol=sym,
                interval=self.interval,
                interval_start=start,
                interval_end=end,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=vol,
                tick_count=1,
                last_tick_time=ts,
            )
            return None

        # Check if tick belongs to a new bucket
        if ts >= current.interval_end:
            # Finalize previous completed interval
            closed_bar = self._finalize_bar(current)

            # Start new bucket
            start, end = self._get_bucket_window(ts)
            self._current_bars[sym] = IncompleteBar(
                symbol=sym,
                interval=self.interval,
                interval_start=start,
                interval_end=end,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=vol,
                tick_count=1,
                last_tick_time=ts,
            )
            return closed_bar

        # Same bucket: update running high/low/close/volume
        current.high = max(current.high if current.high is not None else price, price)
        current.low = min(current.low if current.low is not None else price, price)
        current.close = price
        current.volume += vol
        current.tick_count += 1
        current.last_tick_time = ts
        return None

    def _finalize_bar(self, incomplete: IncompleteBar) -> OHLCVBar:
        """Converts IncompleteBar into an immutable closed OHLCVBar."""
        incomplete.is_finalized = True
        bar = OHLCVBar(
            timestamp=incomplete.interval_start,
            open=incomplete.open,
            high=incomplete.high,
            low=incomplete.low,
            close=incomplete.close if incomplete.close is not None else 0.0,
            volume=incomplete.volume,
            symbol=incomplete.symbol,
            last_price=incomplete.close,
        )
        self._completed_bars.append(bar)
        if len(self._completed_bars) > 1000:
            self._completed_bars.pop(0)
        return bar

    def get_incomplete_bar(self, symbol: str) -> Optional[IncompleteBar]:
        """Returns the current ongoing IncompleteBar for symbol. Explicitly is_finalized=False."""
        return self._current_bars.get(symbol)

    def force_close(self, symbol: str) -> Optional[OHLCVBar]:
        """Explicitly forces completion of the current incomplete bar for a symbol."""
        current = self._current_bars.pop(symbol, None)
        if current and current.tick_count > 0:
            return self._finalize_bar(current)
        return None

    # Aliases for convenience
    on_tick = add_tick
    finalize_bar = force_close

    def flush_all(self) -> List[OHLCVBar]:
        """Forces completion of all open buckets and returns finalized bars."""
        closed: List[OHLCVBar] = []
        for sym in list(self._current_bars.keys()):
            bar = self.force_close(sym)
            if bar:
                closed.append(bar)
        return closed

    def reset(self) -> None:
        """Clears all running state."""
        self._current_bars.clear()
        self._completed_bars.clear()
