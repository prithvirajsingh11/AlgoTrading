"""Tests for structured DatasetValidator and ValidationReport."""

import pandas as pd
from datetime import datetime
from backend.app.research.validator import DatasetValidator


def _valid_df(periods: int = 20) -> pd.DataFrame:
    dates = pd.date_range("2023-01-01", periods=periods)
    prices = [100.0 + i for i in range(periods)]
    return pd.DataFrame({
        "timestamp": dates,
        "open": prices,
        "high": [p + 2.0 for p in prices],
        "low": [p - 2.0 for p in prices],
        "close": prices,
        "volume": [1000] * periods,
    })


def test_validator_clean_dataset():
    df = _valid_df()
    report = DatasetValidator.validate(df)
    assert report.valid is True
    assert report.rows == 20
    assert len(report.errors) == 0


def test_validator_empty_dataset():
    report = DatasetValidator.validate(pd.DataFrame())
    assert report.valid is False
    assert report.rows == 0
    assert any("empty or null" in e for e in report.errors)


def test_validator_missing_columns():
    df = pd.DataFrame({"timestamp": [datetime(2023, 1, 1)], "open": [100.0]})
    report = DatasetValidator.validate(df)
    assert report.valid is False
    assert any("Missing required columns" in e for e in report.errors)


def test_validator_duplicate_timestamps():
    df = _valid_df()
    # duplicate first row
    dup_df = pd.concat([df, df.iloc[[0]]]).reset_index(drop=True)
    report = DatasetValidator.validate(dup_df)
    assert report.valid is False
    assert any("duplicate timestamps" in e for e in report.errors)


def test_validator_unsorted_timestamps():
    df = _valid_df()
    shuffled = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
    report = DatasetValidator.validate(shuffled)
    assert report.valid is False
    assert any("chronological" in e for e in report.errors)


def test_validator_invalid_ohlc_relationships():
    df = _valid_df()
    # Corrupt a row where High < Low
    df.loc[3, "high"] = 80.0
    df.loc[3, "low"] = 120.0
    report = DatasetValidator.validate(df)
    assert report.valid is False
    assert any("High < Low" in e for e in report.errors)


def test_validator_non_positive_price_and_negative_volume():
    df = _valid_df()
    df.loc[2, "close"] = -5.0
    df.loc[4, "volume"] = -100
    report = DatasetValidator.validate(df)
    assert report.valid is False
    assert any("non-positive" in e for e in report.errors)
    assert any("negative" in e for e in report.errors)


def test_validator_extreme_jump_warning():
    df = _valid_df()
    # 100% price spike in single bar
    df.loc[10, "close"] = df.loc[9, "close"] * 2.1
    df.loc[10, "high"] = df.loc[10, "close"] + 1.0
    report = DatasetValidator.validate(df, extreme_jump_threshold=0.50)
    # Warnings do not invalidate dataset
    assert report.valid is True
    assert len(report.warnings) > 0
    assert any("suspicious price jumps" in w for w in report.warnings)
