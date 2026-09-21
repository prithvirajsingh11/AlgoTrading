from typing import List, Tuple
import pandas as pd


class DataValidationError(ValueError):
    """Raised when market data fails integrity or schema validation."""
    pass


class DataChronologyError(DataValidationError):
    """Raised when market data timestamps are out of chronological order."""
    pass


class DataIntegrityError(DataValidationError):
    """Raised when market data contains invalid price/volume relationships."""
    pass


class DataValidator:
    """Validates historical market data integrity and consistency."""

    @staticmethod
    def validate(df: pd.DataFrame, strict: bool = True) -> Tuple[bool, List[str]]:
        """Validates market data.

        Returns (is_valid, list_of_errors). If strict is True, raises exception on first error.
        """
        errors: List[str] = []

        if df.empty:
            msg = "Dataset is empty."
            if strict:
                raise DataValidationError(msg)
            return False, [msg]

        # 1. Missing timestamps
        null_ts_count = df["timestamp"].isna().sum()
        if null_ts_count > 0:
            errors.append(f"Found {null_ts_count} rows with missing timestamps.")

        # 2. Duplicate timestamps
        dup_count = df["timestamp"].duplicated().sum()
        if dup_count > 0:
            errors.append(f"Found {dup_count} duplicate timestamp records.")

        # 3. Missing values in OHLCV
        for col in ["open", "high", "low", "close", "volume"]:
            null_count = df[col].isna().sum()
            if null_count > 0:
                errors.append(f"Found {null_count} missing values in column '{col}'.")

        # 4. Incorrect ordering (monotonicity)
        if not df["timestamp"].is_monotonic_increasing:
            errors.append("Timestamps are not strictly in chronological ascending order.")

        # 5. Invalid OHLC relationships
        # high >= max(open, close) and low <= min(open, close)
        invalid_high = df[(df["high"] < df["open"]) | (df["high"] < df["close"]) | (df["high"] < df["low"])]
        if len(invalid_high) > 0:
            errors.append(f"Found {len(invalid_high)} rows where 'high' is lower than open, close, or low.")

        invalid_low = df[(df["low"] > df["open"]) | (df["low"] > df["close"])]
        if len(invalid_low) > 0:
            errors.append(f"Found {len(invalid_low)} rows where 'low' is higher than open or close.")

        # 6. Non-positive prices and negative volumes
        non_positive_price = df[(df["open"] <= 0) | (df["high"] <= 0) | (df["low"] <= 0) | (df["close"] <= 0)]
        if len(non_positive_price) > 0:
            errors.append(f"Found {len(non_positive_price)} rows with non-positive prices (<= 0).")

        negative_vol = df[df["volume"] < 0]
        if len(negative_vol) > 0:
            errors.append(f"Found {len(negative_vol)} rows with negative volume.")

        if errors and strict:
            if any("chronological" in e for e in errors):
                raise DataChronologyError("; ".join(errors))
            if any("high" in e or "low" in e or "non-positive" in e or "negative" in e for e in errors):
                raise DataIntegrityError("; ".join(errors))
            raise DataValidationError("; ".join(errors))

        return len(errors) == 0, errors


def clean_and_validate(
    df: pd.DataFrame,
    drop_duplicates: bool = False,
    sort_chronological: bool = False,
    strict: bool = True
) -> pd.DataFrame:
    """Cleans and validates OHLCV DataFrame."""
    cleaned = df.copy()

    if drop_duplicates:
        cleaned = cleaned.drop_duplicates(subset=["timestamp"], keep="last")

    if sort_chronological:
        cleaned = cleaned.sort_values(by="timestamp").reset_index(drop=True)

    DataValidator.validate(cleaned, strict=strict)
    return cleaned


def synchronize_pair_datasets(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    symbol_a: str = "ASSET_A",
    symbol_b: str = "ASSET_B",
    policy: str = "intersection",
    strict: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame, List["MarketSnapshot"]]:
    """Synchronizes two historical OHLCV datasets strictly on common/intersection timestamps.

    Deterministic Policy:
    - 'intersection': Evaluates signals only when valid observations exist for both assets at timestamp t.

    Validates:
    - missing pair timestamps
    - duplicate timestamps
    - unsorted timestamps
    - mismatched timestamps
    - missing prices (NaNs)
    """
    from backend.app.data.loader import CSVDataLoader, MarketSnapshot

    if policy != "intersection":
        raise ValueError(f"Unsupported synchronization policy: '{policy}'. Supported policies: ['intersection']")

    if df_a is None or df_b is None or df_a.empty or df_b.empty:
        raise DataValidationError(f"Cannot synchronize empty dataset for {symbol_a} and {symbol_b}.")

    # 1. Clean individual series
    clean_a = clean_and_validate(df_a, strict=strict)
    clean_b = clean_and_validate(df_b, strict=strict)

    # 2. Extract timestamps
    clean_a = clean_a.copy()
    clean_b = clean_b.copy()
    clean_a["timestamp"] = pd.to_datetime(clean_a["timestamp"])
    clean_b["timestamp"] = pd.to_datetime(clean_b["timestamp"])

    ts_a = set(clean_a["timestamp"])
    ts_b = set(clean_b["timestamp"])

    # 3. Intersection of timestamps
    common_ts = sorted(list(ts_a.intersection(ts_b)))
    if not common_ts:
        raise DataValidationError(f"No common timestamps found between {symbol_a} and {symbol_b}.")

    # 4. Filter to common timestamps and ensure strictly sorted
    aligned_a = clean_a[clean_a["timestamp"].isin(common_ts)].sort_values(by="timestamp").reset_index(drop=True)
    aligned_b = clean_b[clean_b["timestamp"].isin(common_ts)].sort_values(by="timestamp").reset_index(drop=True)

    # 5. Build MarketSnapshots
    bars_a = CSVDataLoader.to_bars(aligned_a)
    bars_b = CSVDataLoader.to_bars(aligned_b)

    snapshots: List[MarketSnapshot] = []
    for bar_a, bar_b in zip(bars_a, bars_b):
        if bar_a.timestamp != bar_b.timestamp:
            raise DataChronologyError(f"Timestamp alignment mismatch: {bar_a.timestamp} != {bar_b.timestamp}")
        snapshots.append(
            MarketSnapshot(
                timestamp=bar_a.timestamp,
                bars={symbol_a: bar_a, symbol_b: bar_b},
            )
        )

    return aligned_a, aligned_b, snapshots
