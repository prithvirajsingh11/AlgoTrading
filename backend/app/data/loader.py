from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Union, Optional
import pandas as pd


@dataclass(frozen=True)
class OHLCVBar:
    """Represents a single chronological OHLCV bar or normalized quote observation."""
    timestamp: datetime
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: float = 0.0
    volume: Optional[float] = None
    symbol: Optional[str] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    last_price: Optional[float] = None

    @property
    def mid(self) -> Optional[float]:
        """Returns mid price if both bid and ask are available."""
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / 2.0
        return None

    def to_dict(self) -> dict:
        res = {
            "timestamp": self.timestamp.isoformat() if hasattr(self.timestamp, "isoformat") else str(self.timestamp),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }
        if self.symbol:
            res["symbol"] = self.symbol
        if self.bid is not None:
            res["bid"] = self.bid
        if self.ask is not None:
            res["ask"] = self.ask
        if self.mid is not None:
            res["mid"] = self.mid
        if self.last_price is not None:
            res["last_price"] = self.last_price
        return res


@dataclass(frozen=True)
class MarketSnapshot:
    """Represents a synchronized multi-asset market observation at timestamp t."""
    timestamp: datetime
    bars: dict[str, OHLCVBar]
    received_at: Optional[datetime] = None

    def get_bar(self, symbol: str) -> Optional[OHLCVBar]:
        return self.bars.get(symbol)

    def __getitem__(self, symbol: str) -> OHLCVBar:
        return self.bars[symbol]

    def __contains__(self, symbol: str) -> bool:
        return symbol in self.bars

    @property
    def latency_ms(self) -> Optional[float]:
        """Calculates latency between market timestamp and server receive timestamp."""
        if self.received_at is not None and self.timestamp is not None:
            try:
                r_ts = self.received_at.timestamp()
                m_ts = self.timestamp.timestamp()
                return max(0.0, round((r_ts - m_ts) * 1000.0, 2))
            except Exception:
                return None
        return None

    def to_dict(self) -> dict:
        res = {
            "timestamp": self.timestamp.isoformat() if hasattr(self.timestamp, "isoformat") else str(self.timestamp),
            "bars": {sym: bar.to_dict() for sym, bar in self.bars.items()},
        }
        if self.received_at:
            res["received_at"] = self.received_at.isoformat() if hasattr(self.received_at, "isoformat") else str(self.received_at)
        lat = self.latency_ms
        if lat is not None:
            res["latency_ms"] = lat
        return res


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

        cols = self.STANDARD_COLUMNS + (["symbol"] if "symbol" in df.columns else [])
        return df[cols]

    @staticmethod
    def to_bars(df: pd.DataFrame, symbol: Optional[str] = None) -> List[OHLCVBar]:
        bars: List[OHLCVBar] = []
        sym_col = "symbol" if "symbol" in df.columns else None
        for row in df.itertuples(index=False):
            ts = getattr(row, "timestamp")
            if isinstance(ts, pd.Timestamp):
                ts = ts.to_pydatetime()
            row_sym = getattr(row, sym_col) if sym_col else symbol
            bars.append(
                OHLCVBar(
                    timestamp=ts,
                    open=float(getattr(row, "open")),
                    high=float(getattr(row, "high")),
                    low=float(getattr(row, "low")),
                    close=float(getattr(row, "close")),
                    volume=float(getattr(row, "volume")),
                    symbol=str(row_sym) if row_sym is not None else None,
                )
            )
        return bars
