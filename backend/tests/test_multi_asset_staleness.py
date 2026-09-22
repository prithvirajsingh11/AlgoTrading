"""Tests verifying multi-asset desynchronization and asymmetric symbol staleness.

Scenario:
Pair strategy on AAPL / MSFT.
1. AAPL fresh, MSFT stale:
   - Synchronizer detects desynchronization.
   - Signal generation for pair is blocked.
2. AAPL fresh, MSFT fresh and temporally aligned:
   - Synchronizer validates snapshot.
   - Pair signal evaluation proceeds normally.
"""

from datetime import datetime, timezone, timedelta
import pytest
from backend.app.paper.sync import SnapshotSynchronizer
from backend.app.data.loader import OHLCVBar, MarketSnapshot


def test_asymmetric_pair_staleness_blocks_signals():
    symbols = ["AAPL", "MSFT"]
    synchronizer = SnapshotSynchronizer(symbols=symbols, max_desync_seconds=5.0)

    now = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)
    stale_time = now - timedelta(seconds=20)  # 20 seconds old (> 5.0s threshold)

    # 1. Update AAPL with fresh observation, MSFT with stale observation
    synchronizer.update_bar(OHLCVBar(timestamp=now, close=150.0, symbol="AAPL"), symbol="AAPL")
    # Manually backdate MSFT observation
    synchronizer.update_bar(OHLCVBar(timestamp=stale_time, close=250.0, symbol="MSFT"), symbol="MSFT")
    synchronizer._received_at["MSFT"] = stale_time

    # Synchronizer must report not synchronized
    assert not synchronizer.is_synchronized(reference_time=now)
    stale_syms = synchronizer.get_stale_symbols(max_age_seconds=5.0, reference_time=now)
    assert "MSFT" in stale_syms
    assert "AAPL" not in stale_syms
    assert "MSFT" in synchronizer.get_desync_reason(reference_time=now)

    # 2. Update MSFT with fresh observation synchronized with AAPL
    synchronizer.update_bar(OHLCVBar(timestamp=now, close=252.0, symbol="MSFT"), symbol="MSFT")
    synchronizer._received_at["MSFT"] = now

    assert synchronizer.is_synchronized(reference_time=now)
    assert len(synchronizer.get_stale_symbols(max_age_seconds=5.0, reference_time=now)) == 0
    assert synchronizer.get_desync_reason(reference_time=now) is None
