import pytest
import pandas as pd
from backend.app.data.loader import CSVDataLoader, OHLCVBar
from backend.app.data.cleaner import (
    DataValidator,
    DataValidationError,
    DataChronologyError,
    DataIntegrityError,
    clean_and_validate,
)


def get_valid_df():
    return pd.DataFrame({
        "timestamp": pd.date_range("2023-01-01", periods=5),
        "open": [100.0, 101.0, 102.0, 103.0, 104.0],
        "high": [105.0, 106.0, 107.0, 108.0, 109.0],
        "low": [98.0, 99.0, 100.0, 101.0, 102.0],
        "close": [102.0, 103.0, 104.0, 105.0, 106.0],
        "volume": [1000, 2000, 1500, 1800, 2100],
    })


def test_valid_data_validation():
    df = get_valid_df()
    is_valid, errors = DataValidator.validate(df, strict=True)
    assert is_valid
    assert len(errors) == 0

    bars = CSVDataLoader.to_bars(df)
    assert len(bars) == 5
    assert isinstance(bars[0], OHLCVBar)
    assert bars[0].close == 102.0


def test_missing_timestamps():
    df = get_valid_df()
    df.loc[2, "timestamp"] = None
    with pytest.raises(DataValidationError, match="missing timestamps"):
        DataValidator.validate(df, strict=True)


def test_duplicate_timestamps():
    df = get_valid_df()
    df.loc[2, "timestamp"] = df.loc[1, "timestamp"]
    with pytest.raises(DataValidationError, match="duplicate timestamp"):
        DataValidator.validate(df, strict=True)


def test_invalid_ohlc_high_lower_than_low():
    df = get_valid_df()
    df.loc[1, "high"] = 95.0  # high (95) < low (99)
    with pytest.raises(DataIntegrityError, match="lower than open, close, or low"):
        DataValidator.validate(df, strict=True)


def test_negative_price():
    df = get_valid_df()
    df.loc[3, "close"] = -10.0
    with pytest.raises(DataIntegrityError, match="non-positive prices"):
        DataValidator.validate(df, strict=True)


def test_negative_volume():
    df = get_valid_df()
    df.loc[3, "volume"] = -500
    with pytest.raises(DataIntegrityError, match="negative volume"):
        DataValidator.validate(df, strict=True)


def test_missing_values_nan():
    df = get_valid_df()
    df.loc[2, "close"] = float("nan")
    with pytest.raises(DataValidationError, match="missing values in column 'close'"):
        DataValidator.validate(df, strict=True)


def test_out_of_chronological_order():
    df = get_valid_df()
    # Reverse order
    df = df.iloc[::-1].reset_index(drop=True)
    with pytest.raises(DataChronologyError, match="chronological ascending order"):
        DataValidator.validate(df, strict=True)


def test_clean_and_validate_heals_ordering_and_duplicates():
    df = get_valid_df()
    # add duplicate and shuffle
    dup_row = df.iloc[[1]].copy()
    corrupt_df = pd.concat([df, dup_row]).iloc[::-1]

    cleaned = clean_and_validate(corrupt_df, drop_duplicates=True, sort_chronological=True, strict=True)
    assert len(cleaned) == 5
    assert cleaned["timestamp"].is_monotonic_increasing
