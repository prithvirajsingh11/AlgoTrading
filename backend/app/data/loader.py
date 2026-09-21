from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Union, Optional
import pandas as pd


@dataclass(frozen=True)
class OHLCVBar:
    """Represents a single chronological OHLCV bar."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


class CSVDataLoader:
    """Loads historical OHLCV data from local CSV storage."""

    STANDARD_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]

    COLUMN_MAPPINGS = {
        "date": "timestamp",
        "datetime": "timestamp",
        "time": "timestamp",
        "adj close": "adj_close",
        "vol": "volume",
    }

    def load_csv(self, filepath: Union[str, Path]) -> pd.DataFrame:
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Historical data file not found at: {path}")

        df = pd.read_csv(path)
        return self.normalize_dataframe(df)

    def normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.columns = [col.strip().lower() for col in df.columns]
        df.rename(columns=self.COLUMN_MAPPINGS, inplace=True)

        missing_cols = [col for col in self.STANDARD_COLUMNS if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns in CSV: {missing_cols}")

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return df[self.STANDARD_COLUMNS]

    @staticmethod
    def to_bars(df: pd.DataFrame) -> List[OHLCVBar]:
        bars: List[OHLCVBar] = []
        for row in df.itertuples(index=False):
            ts = row.timestamp
            if isinstance(ts, pd.Timestamp):
                ts = ts.to_pydatetime()
            bars.append(
                OHLCVBar(
                    timestamp=ts,
                    open=float(row.open),
                    high=float(row.high),
                    low=float(row.low),
                    close=float(row.close),
                    volume=float(row.volume),
                )
            )
        return bars
