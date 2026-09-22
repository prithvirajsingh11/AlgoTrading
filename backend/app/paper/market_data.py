"""Market Data Provider architecture for Paper Trading.

Includes abstract MarketDataProvider interface and deterministic HistoricalReplayProvider.
Enforces zero lookahead: future bars are inaccessible to the caller.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
import pandas as pd

from backend.app.data.loader import OHLCVBar, MarketSnapshot, CSVDataLoader
from backend.app.research.dataset import DatasetManager


class MarketDataProvider(ABC):
    """Abstract interface for paper-trading market data feeds."""

    @abstractmethod
    def start(self) -> None:
        """Initializes feed."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Closes feed."""
        pass

    @abstractmethod
    def has_next(self) -> bool:
        """Returns True if more bars/snapshots are available."""
        pass

    @abstractmethod
    def next_snapshot(self) -> Tuple[int, MarketSnapshot, Dict[str, OHLCVBar]]:
        """Advances stream by one timestamp and returns (index, snapshot, bars_dict)."""
        pass

    @abstractmethod
    def get_total_bars(self) -> int:
        """Returns total historical bars available in stream."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Resets replay cursor to beginning."""
        pass


class HistoricalReplayProvider(MarketDataProvider):
    """Replays historical market data bar-by-bar in strict chronological order."""

    def __init__(
        self,
        dataset_id: str,
        symbols: Optional[List[str]] = None,
        dataset_manager: Optional[DatasetManager] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ):
        self.dataset_id = dataset_id
        self.symbols = symbols or [dataset_id]
        self.dataset_manager = dataset_manager or DatasetManager()
        self.start_date = start_date
        self.end_date = end_date

        self.snapshots: List[MarketSnapshot] = []
        self._cursor: int = 0
        self._is_active: bool = False
        self.aligned_data: Dict[str, pd.DataFrame] = {}

        self._load_and_prepare_data()

    def _load_and_prepare_data(self) -> None:
        """Loads data from DatasetManager and constructs synchronized MarketSnapshots."""
        from backend.app.data.cleaner import clean_and_validate, synchronize_pair_datasets

        raw_frames: Dict[str, pd.DataFrame] = {}
        if len(self.symbols) > 1:
            for sym in self.symbols:
                df = self.dataset_manager.load_dataset(sym)
                raw_frames[sym] = df
        else:
            primary_sym = self.symbols[0]
            df = self.dataset_manager.load_dataset(self.dataset_id)
            raw_frames[primary_sym] = df

        # Apply date filters if specified
        for sym in raw_frames:
            df = raw_frames[sym]
            if self.start_date:
                df = df[df["timestamp"] >= self.start_date].reset_index(drop=True)
            if self.end_date:
                df = df[df["timestamp"] <= self.end_date].reset_index(drop=True)
            raw_frames[sym] = df

        # Build chronological snapshots and cleaned aligned frames
        if len(self.symbols) == 1:
            sym = self.symbols[0]
            cleaned_df = clean_and_validate(raw_frames[sym], strict=True)
            self.aligned_data[sym] = cleaned_df
            bars = CSVDataLoader.to_bars(cleaned_df, symbol=sym)
            self.snapshots = [
                MarketSnapshot(timestamp=b.timestamp, bars={sym: b})
                for b in bars
            ]
        elif len(self.symbols) == 2:
            s1, s2 = self.symbols[0], self.symbols[1]
            synced_a, synced_b, snapshots = synchronize_pair_datasets(
                raw_frames[s1], raw_frames[s2], symbol_a=s1, symbol_b=s2
            )
            self.aligned_data[s1] = synced_a
            self.aligned_data[s2] = synced_b
            self.snapshots = snapshots
        else:
            common_timestamps = None
            for sym in self.symbols:
                c_df = clean_and_validate(raw_frames[sym], strict=True)
                self.aligned_data[sym] = c_df
                ts_set = set(c_df["timestamp"])
                common_timestamps = ts_set if common_timestamps is None else common_timestamps.intersection(ts_set)
            common_list = sorted(list(common_timestamps or []))
            for sym in self.symbols:
                self.aligned_data[sym] = (
                    self.aligned_data[sym][self.aligned_data[sym]["timestamp"].isin(common_list)]
                    .sort_values(by="timestamp")
                    .reset_index(drop=True)
                )
            timestamps = self.aligned_data[self.symbols[0]]["timestamp"]
            bars_by_sym = {sym: CSVDataLoader.to_bars(self.aligned_data[sym], symbol=sym) for sym in self.symbols}
            self.snapshots = [
                MarketSnapshot(timestamp=ts, bars={sym: bars_by_sym[sym][i] for sym in self.symbols})
                for i, ts in enumerate(timestamps)
            ]

    def get_slice(self, up_to_index: int) -> Any:
        """Returns historical slice up to up_to_index (zero lookahead)."""
        idx = min(up_to_index + 1, len(self.snapshots))
        if len(self.symbols) == 1:
            sym = self.symbols[0]
            return self.aligned_data[sym].iloc[:idx]
        return {sym: self.aligned_data[sym].iloc[:idx] for sym in self.symbols}

    def is_multi_asset(self) -> bool:
        return len(self.symbols) > 1

    def start(self) -> None:
        self._is_active = True

    def stop(self) -> None:
        self._is_active = False

    def reset(self) -> None:
        self._cursor = 0
        self._is_active = False

    def has_next(self) -> bool:
        return self._cursor < len(self.snapshots)

    def next_snapshot(self) -> Tuple[int, MarketSnapshot, Dict[str, OHLCVBar]]:
        if not self.has_next():
            raise IndexError("HistoricalReplayProvider stream exhausted.")

        idx = self._cursor
        snapshot = self.snapshots[idx]
        self._cursor += 1
        return idx, snapshot, snapshot.bars

    def get_total_bars(self) -> int:
        return len(self.snapshots)

    @property
    def current_index(self) -> int:
        return self._cursor


# Re-export streaming components for convenient unified import
from backend.app.paper.realtime import (
    ConnectionState,
    ProviderStatus,
    BaseProviderAdapter,
    InMemoryStreamingAdapter,
    GenericWebSocketAdapter,
    AlpacaMarketDataAdapter,
    RealTimeMarketDataProvider,
    MarketTick,
)

