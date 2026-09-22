"""Streaming Feature Engine for real-time paper trading.

Enforces:
1. Reuses existing FeatureEngineer implementation (zero duplicated indicators).
2. Maintains bounded historical rolling buffers (constant memory, fast incremental evaluation).
3. Zero lookahead: features at time t strictly depend only on observations <= t.
"""

from __future__ import annotations
from collections import deque
from typing import Dict, List, Optional, Any, Union
import pandas as pd

from backend.app.data.loader import OHLCVBar, MarketSnapshot
from backend.app.ml.features import FeatureEngineer, FeatureConfig


class StreamingFeatureEngine:
    """Maintains bounded rolling bar buffers and computes features incrementally."""

    def __init__(
        self,
        symbols: List[str],
        feature_config: Optional[FeatureConfig] = None,
        max_buffer_size: int = 150,
    ):
        self.symbols = list(symbols)
        self.feature_engineer = FeatureEngineer(feature_config or FeatureConfig())
        self.max_buffer_size = max(max_buffer_size, self.feature_engineer.warmup_bars + 20)
        self._buffers: Dict[str, deque] = {s: deque(maxlen=self.max_buffer_size) for s in self.symbols}

    @property
    def warmup_bars(self) -> int:
        return self.feature_engineer.warmup_bars

    def update_bar(self, bar: OHLCVBar, symbol: Optional[str] = None) -> None:
        """Appends incoming bar to rolling buffer."""
        sym = symbol or bar.symbol
        if not sym:
            return
        if sym not in self._buffers:
            self._buffers[sym] = deque(maxlen=self.max_buffer_size)

        open_val = bar.open if bar.open is not None else bar.close
        high_val = bar.high if bar.high is not None else bar.close
        low_val = bar.low if bar.low is not None else bar.close
        vol_val = bar.volume if bar.volume is not None else 0.0

        self._buffers[sym].append({
            "timestamp": bar.timestamp,
            "open": float(open_val),
            "high": float(high_val),
            "low": float(low_val),
            "close": float(bar.close),
            "volume": float(vol_val),
        })

    def update_snapshot(self, snapshot: MarketSnapshot) -> None:
        """Appends all bars from an incoming snapshot to their respective rolling buffers."""
        for sym, bar in snapshot.bars.items():
            self.update_bar(bar, symbol=sym)

    def is_warmed_up(self, symbol: Optional[str] = None) -> bool:
        """Checks if enough historical bars have accumulated for indicator calculation."""
        if symbol is not None:
            return len(self._buffers.get(symbol, [])) >= self.warmup_bars
        return all(len(buf) >= self.warmup_bars for buf in self._buffers.values())

    def get_history_df(self, symbol: str) -> pd.DataFrame:
        """Returns bounded historical slice DataFrame strictly up to current observation."""
        buf = self._buffers.get(symbol)
        if not buf:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        return pd.DataFrame(list(buf))

    def get_all_history_dfs(self) -> Dict[str, pd.DataFrame]:
        """Returns bounded history DataFrames for all tracked symbols."""
        return {s: self.get_history_df(s) for s in self.symbols}

    def compute_latest_features(self, symbol: str) -> pd.DataFrame:
        """Computes feature vector for latest bar of given symbol without lookahead."""
        df = self.get_history_df(symbol)
        if len(df) < self.warmup_bars:
            return pd.DataFrame()
        return self.feature_engineer.compute_bar_features(df)

    def clear(self) -> None:
        """Clears all rolling buffers."""
        for buf in self._buffers.values():
            buf.clear()
