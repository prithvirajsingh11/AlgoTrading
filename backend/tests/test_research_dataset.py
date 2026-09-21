"""Tests for DatasetMetadata and DatasetManager."""

from datetime import datetime, timezone
import pandas as pd
import pytest
from backend.app.research.dataset import DatasetMetadata, DatasetManager


def test_dataset_metadata_serialization():
    dt = datetime(2023, 1, 1, tzinfo=timezone.utc)
    meta = DatasetMetadata(
        dataset_id="TEST_DS",
        symbols=["AAPL", "MSFT"],
        timeframe="1d",
        start_timestamp=dt,
        end_timestamp=dt,
        row_count=100,
        source="csv",
        validation_status="valid",
    )
    d = meta.to_dict()
    assert d["dataset_id"] == "TEST_DS"
    assert d["symbols"] == ["AAPL", "MSFT"]
    assert d["row_count"] == 100

    restored = DatasetMetadata.from_dict(d)
    assert restored.dataset_id == meta.dataset_id
    assert restored.symbols == meta.symbols
    assert restored.row_count == meta.row_count
    assert restored.validation_status == "valid"


def test_dataset_manager_discovery_and_load(tmp_path):
    # Create sample CSV
    csv_file = tmp_path / "TSLA_sample.csv"
    df = pd.DataFrame({
        "timestamp": pd.date_range("2023-01-01", periods=10),
        "open": [100.0 + i for i in range(10)],
        "high": [105.0 + i for i in range(10)],
        "low": [95.0 + i for i in range(10)],
        "close": [101.0 + i for i in range(10)],
        "volume": [1000] * 10,
    })
    df.to_csv(csv_file, index=False)

    manager = DatasetManager(raw_data_dir=tmp_path)
    datasets = manager.discover_datasets()
    assert len(datasets) == 1
    assert datasets[0].dataset_id == "TSLA_sample"
    assert datasets[0].symbols == ["TSLA"]
    assert datasets[0].row_count == 10

    loaded_df = manager.load_dataset("TSLA_sample")
    assert len(loaded_df) == 10
    assert "close" in loaded_df.columns


def test_dataset_manager_in_memory_registration():
    manager = DatasetManager()
    df = pd.DataFrame({
        "timestamp": pd.date_range("2023-01-01", periods=5),
        "open": [10.0] * 5,
        "high": [11.0] * 5,
        "low": [9.0] * 5,
        "close": [10.0] * 5,
        "volume": [500] * 5,
    })
    meta = manager.register_in_memory_dataset("SYNTHETIC_1", df, symbols=["SYN"])
    assert meta.dataset_id == "SYNTHETIC_1"
    assert meta.row_count == 5

    loaded = manager.load_dataset("SYNTHETIC_1")
    assert len(loaded) == 5
    assert manager.get_dataset_metadata("SYNTHETIC_1").dataset_id == "SYNTHETIC_1"
