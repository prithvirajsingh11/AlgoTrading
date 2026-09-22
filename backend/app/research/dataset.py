"""Dataset management and metadata abstraction for algorithmic research.

Supports dataset discovery, metadata inspection, and format-agnostic loading
(CSV default, extensible to Parquet).
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Union
import pandas as pd

from backend.app.core.config import settings
from backend.app.data.loader import CSVDataLoader


@dataclass
class DatasetMetadata:
    """Metadata representation for a registered historical dataset."""

    dataset_id: str
    symbols: List[str]
    timeframe: str = "1d"
    start_timestamp: Optional[datetime] = None
    end_timestamp: Optional[datetime] = None
    row_count: int = 0
    source: str = "csv"
    validation_status: str = "unvalidated"  # "unvalidated", "valid", "invalid"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    file_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Union[str, int, List[str], None]]:
        return {
            "dataset_id": self.dataset_id,
            "symbols": self.symbols,
            "timeframe": self.timeframe,
            "start_timestamp": self.start_timestamp.isoformat() if hasattr(self.start_timestamp, "isoformat") else (str(self.start_timestamp) if self.start_timestamp else None),
            "end_timestamp": self.end_timestamp.isoformat() if hasattr(self.end_timestamp, "isoformat") else (str(self.end_timestamp) if self.end_timestamp else None),
            "row_count": self.row_count,
            "source": self.source,
            "validation_status": self.validation_status,
            "created_at": self.created_at.isoformat() if hasattr(self.created_at, "isoformat") else (str(self.created_at) if self.created_at else None),
            "file_path": str(self.file_path) if self.file_path else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Union[str, int, List[str], None]]) -> DatasetMetadata:
        st = data.get("start_timestamp")
        et = data.get("end_timestamp")
        ca = data.get("created_at")
        symbols = data.get("symbols", [])
        if isinstance(symbols, str):
            symbols = [symbols]

        return cls(
            dataset_id=str(data["dataset_id"]),
            symbols=list(symbols),
            timeframe=str(data.get("timeframe", "1d")),
            start_timestamp=datetime.fromisoformat(str(st)) if st else None,
            end_timestamp=datetime.fromisoformat(str(et)) if et else None,
            row_count=int(data.get("row_count", 0)),
            source=str(data.get("source", "csv")),
            validation_status=str(data.get("validation_status", "unvalidated")),
            created_at=datetime.fromisoformat(str(ca)) if ca else datetime.now(timezone.utc),
            file_path=str(data["file_path"]) if data.get("file_path") else None,
        )


class DatasetManager:
    """Manages dataset discovery, indexing, metadata generation, and loading."""

    def __init__(self, raw_data_dir: Optional[Path] = None):
        self.raw_data_dir = raw_data_dir or (settings.data_dir / "raw")
        self._in_memory_datasets: Dict[str, pd.DataFrame] = {}
        self._custom_metadata: Dict[str, DatasetMetadata] = {}

    def register_in_memory_dataset(
        self,
        dataset_id: str,
        df: pd.DataFrame,
        symbols: Optional[List[str]] = None,
        timeframe: str = "1d",
    ) -> DatasetMetadata:
        """Registers an in-memory DataFrame as a named dataset."""
        df_sorted = df.sort_values(by="timestamp").reset_index(drop=True)
        self._in_memory_datasets[dataset_id] = df_sorted

        if symbols is None:
            if "symbol" in df_sorted.columns:
                symbols = sorted(list(df_sorted["symbol"].dropna().unique()))
            else:
                symbols = [dataset_id.split("_")[0].upper()]

        start_ts = df_sorted["timestamp"].min()
        end_ts = df_sorted["timestamp"].max()
        if isinstance(start_ts, pd.Timestamp):
            start_ts = start_ts.to_pydatetime()
        if isinstance(end_ts, pd.Timestamp):
            end_ts = end_ts.to_pydatetime()

        meta = DatasetMetadata(
            dataset_id=dataset_id,
            symbols=symbols,
            timeframe=timeframe,
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            row_count=len(df_sorted),
            source="in_memory",
            validation_status="unvalidated",
            created_at=datetime.now(timezone.utc),
            file_path=None,
        )
        self._custom_metadata[dataset_id] = meta
        return meta

    register_dataframe = register_in_memory_dataset

    def discover_datasets(self) -> List[DatasetMetadata]:
        """Scans raw_data_dir and indexed in-memory datasets, returning metadata list."""
        discovered: List[DatasetMetadata] = []

        # 1. In-memory datasets
        for meta in self._custom_metadata.values():
            discovered.append(meta)

        # 2. Files on disk
        if self.raw_data_dir.exists():
            # CSV files
            for file_path in sorted(self.raw_data_dir.glob("*.csv")):
                dataset_id = file_path.stem
                if dataset_id in self._custom_metadata:
                    continue
                meta = self._inspect_file_dataset(file_path, source="csv")
                discovered.append(meta)

            # Extensible: Parquet files
            for file_path in sorted(self.raw_data_dir.glob("*.parquet")):
                dataset_id = file_path.stem
                if dataset_id in self._custom_metadata:
                    continue
                meta = self._inspect_file_dataset(file_path, source="parquet")
                discovered.append(meta)

        # 3. Demo datasets (only if using default raw_data_dir)
        if self.raw_data_dir == (settings.data_dir / "raw"):
            demo_dir = settings.data_dir / "demo"
            if demo_dir.exists():
                for file_path in sorted(demo_dir.glob("*.csv")):
                    dataset_id = file_path.stem
                    if dataset_id in self._custom_metadata or any(d.dataset_id == dataset_id for d in discovered):
                        continue
                    meta = self._inspect_file_dataset(file_path, source="demo_csv")
                    discovered.append(meta)

        return discovered

    def get_dataset_metadata(self, dataset_id: str) -> Optional[DatasetMetadata]:
        """Retrieves metadata for a specific dataset ID."""
        for meta in self.discover_datasets():
            if meta.dataset_id == dataset_id:
                return meta
        return None

    def load_dataset(self, dataset_id: str) -> pd.DataFrame:
        """Loads dataset by ID into a pandas DataFrame."""
        if dataset_id in self._in_memory_datasets:
            return self._in_memory_datasets[dataset_id].copy()

        # Check raw files on disk
        if self.raw_data_dir.exists():
            csv_path = self.raw_data_dir / f"{dataset_id}.csv"
            if csv_path.exists():
                loader = CSVDataLoader()
                return loader.load_csv(csv_path)

            parquet_path = self.raw_data_dir / f"{dataset_id}.parquet"
            if parquet_path.exists():
                df = pd.read_parquet(parquet_path)
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                return df.sort_values(by="timestamp").reset_index(drop=True)

            # Prefix search e.g. "AAPL" matching "AAPL_sample.csv"
            matches = list(self.raw_data_dir.glob(f"{dataset_id}*.csv"))
            if matches:
                loader = CSVDataLoader()
                return loader.load_csv(matches[0])

        # Check demo files on disk
        demo_dir = settings.data_dir / "demo"
        if demo_dir.exists():
            csv_path = demo_dir / f"{dataset_id}.csv"
            if csv_path.exists():
                loader = CSVDataLoader()
                return loader.load_csv(csv_path)

            matches = list(demo_dir.glob(f"{dataset_id}*.csv"))
            if matches:
                loader = CSVDataLoader()
                return loader.load_csv(matches[0])

        raise FileNotFoundError(f"Dataset '{dataset_id}' not found in {self.raw_data_dir} or {demo_dir}")

    def _inspect_file_dataset(self, file_path: Path, source: str) -> DatasetMetadata:
        dataset_id = file_path.stem
        symbol = "AAPL" if dataset_id.startswith("benchmark") else dataset_id.split("_")[0].upper()
        symbols = [symbol]

        try:
            if source in ("csv", "demo_csv"):
                loader = CSVDataLoader()
                df = loader.load_csv(file_path)
            elif source == "parquet":
                df = pd.read_parquet(file_path)
                df["timestamp"] = pd.to_datetime(df["timestamp"])
            else:
                df = pd.DataFrame()

            if not df.empty and "timestamp" in df.columns:
                start_ts = df["timestamp"].min()
                end_ts = df["timestamp"].max()
                if isinstance(start_ts, pd.Timestamp):
                    start_ts = start_ts.to_pydatetime()
                if isinstance(end_ts, pd.Timestamp):
                    end_ts = end_ts.to_pydatetime()
                row_count = len(df)
            else:
                start_ts, end_ts, row_count = None, None, 0

        except Exception:
            start_ts, end_ts, row_count = None, None, 0

        return DatasetMetadata(
            dataset_id=dataset_id,
            symbols=symbols,
            timeframe="1d",
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            row_count=row_count,
            source=source,
            validation_status="unvalidated",
            created_at=datetime.fromtimestamp(file_path.stat().st_ctime, tz=timezone.utc),
            file_path=str(file_path),
        )
