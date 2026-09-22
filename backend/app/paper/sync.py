"""Multi-asset snapshot synchronization policy for real-time market data.

Enforces:
1. Strict multi-asset synchronization without silent stale-leg execution.
2. Configurable desynchronization threshold (max_desync_seconds).
3. Two-leg pair strategy validation: both legs must be simultaneously fresh.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import logging

from backend.app.data.loader import OHLCVBar, MarketSnapshot

logger = logging.getLogger("market_sync")


class SnapshotSynchronizer:
    """Maintains latest valid observations and enforces multi-asset freshness policies."""

    def __init__(
        self,
        symbols: List[str],
        max_desync_seconds: float = 5.0,
    ):
        self.symbols = list(symbols)
        self.max_desync_seconds = max_desync_seconds
        self._latest_bars: Dict[str, OHLCVBar] = {}
        self._received_at: Dict[str, datetime] = {}

    def update_bar(self, bar: OHLCVBar, symbol: Optional[str] = None) -> None:
        """Records a new observation for a symbol."""
        sym = symbol or bar.symbol
        if not sym:
            return
        self._latest_bars[sym] = bar
        self._received_at[sym] = datetime.now(timezone.utc)

    def update_snapshot(self, snapshot: MarketSnapshot) -> None:
        """Records all bars from an incoming snapshot."""
        recv = snapshot.received_at or datetime.now(timezone.utc)
        for sym, bar in snapshot.bars.items():
            self._latest_bars[sym] = bar
            self._received_at[sym] = recv

    def is_synchronized(self, reference_time: Optional[datetime] = None) -> bool:
        """Verifies that all required symbols have fresh, synchronized observations."""
        reason = self.get_desync_reason(reference_time)
        return reason is None

    def get_desync_reason(self, reference_time: Optional[datetime] = None) -> Optional[str]:
        """Returns explanation if symbols are missing or desynchronized, else None."""
        if not self.symbols:
            return "No symbols configured for synchronization."

        ref = reference_time or datetime.now(timezone.utc)
        ref_ts = ref.timestamp() if hasattr(ref, "timestamp") else 0

        # Check all symbols present
        missing = [s for s in self.symbols if s not in self._latest_bars]
        if missing:
            return f"Missing market observations for symbols: {missing}"

        # Check staleness relative to reference time
        timestamps = []
        for s in self.symbols:
            bar = self._latest_bars[s]
            b_ts = bar.timestamp.timestamp() if hasattr(bar.timestamp, "timestamp") else 0
            age = ref_ts - b_ts
            if age > self.max_desync_seconds:
                return (
                    f"Symbol '{s}' observation is stale ({age:.2f}s old > max allowed "
                    f"{self.max_desync_seconds:.2f}s)"
                )
            timestamps.append(b_ts)

        # Check cross-symbol divergence
        if len(timestamps) > 1:
            divergence = max(timestamps) - min(timestamps)
            if divergence > self.max_desync_seconds:
                return (
                    f"Cross-asset divergence ({divergence:.2f}s) exceeds maximum allowed "
                    f"threshold ({self.max_desync_seconds:.2f}s)"
                )

        return None

    def get_synchronized_snapshot(self, reference_time: Optional[datetime] = None) -> Optional[MarketSnapshot]:
        """Constructs a synchronized MarketSnapshot if freshness policy is met, else None."""
        if not self.is_synchronized(reference_time):
            return None

        # Build snapshot using the latest available timestamp across the legs
        latest_ts = max(self._latest_bars[s].timestamp for s in self.symbols)
        latest_recv = max(self._received_at[s] for s in self.symbols)

        return MarketSnapshot(
            timestamp=latest_ts,
            bars={s: self._latest_bars[s] for s in self.symbols},
            received_at=latest_recv,
        )

    def clear(self) -> None:
        """Clears cached observations."""
        self._latest_bars.clear()
        self._received_at.clear()
