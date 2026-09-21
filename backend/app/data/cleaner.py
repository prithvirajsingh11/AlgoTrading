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
