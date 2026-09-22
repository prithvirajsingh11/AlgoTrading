"""Tests proving the three operational modes are strictly distinct and mutually exclusive.

Modes:
1. HISTORICAL_REPLAY: Uses stored historical datasets.
2. SYNTHETIC_STREAM: Uses InMemoryStreamingAdapter with explicit 'SYNTHETIC TEST FEED' tag.
3. REAL_TIME: Requires configured external provider; fails cleanly to NOT_CONFIGURED when unconfigured.
"""

import tempfile
from pathlib import Path
import pytest

from backend.app.paper.service import PaperTradingService
from backend.app.paper.session import PaperTradingSession, SessionMode, SignalSafetyState
from backend.app.paper.storage import SQLitePaperStorage
from backend.app.paper.market_data import (
    HistoricalReplayProvider,
    InMemoryStreamingAdapter,
    AlpacaMarketDataAdapter,
    ConnectionState,
)
from backend.app.core.config import settings
from backend.app.research.dataset import DatasetManager
import pandas as pd


def test_mode_historical_replay():
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = SQLitePaperStorage(str(Path(tmp_dir) / "test_modes.db"))
        service = PaperTradingService(storage=storage)

        dm = DatasetManager()
        df = pd.DataFrame({
            "timestamp": pd.date_range("2023-01-01", periods=10, freq="D"),
            "open": [100.0] * 10,
            "high": [105.0] * 10,
            "low": [95.0] * 10,
            "close": [102.0] * 10,
            "volume": [1000.0] * 10,
        })
        dm.register_dataframe("test_hist_ds", df, symbols=["AAPL"])

        cfg = {
            "mode": "HISTORICAL_REPLAY",
            "dataset_id": "test_hist_ds",
            "symbols": ["AAPL"],
            "strategy": "TimeSeriesMomentum",
        }
        session = service.create_session(cfg, dataset_manager=dm)
        assert session.mode == SessionMode.HISTORICAL_REPLAY.value
        assert session.data_provider_type == "HISTORICAL"
        assert isinstance(service.providers[session.session_id], HistoricalReplayProvider)


def test_mode_synthetic_stream():
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = SQLitePaperStorage(str(Path(tmp_dir) / "test_modes.db"))
        service = PaperTradingService(storage=storage)

        cfg = {
            "mode": "SYNTHETIC_STREAM",
            "symbols": ["AAPL"],
            "strategy": "TimeSeriesMomentum",
        }
        session = service.create_session(cfg)
        assert session.mode == SessionMode.SYNTHETIC_STREAM.value
        assert session.data_provider_type == "SYNTHETIC"
        provider = service.providers[session.session_id]
        assert isinstance(provider.adapter, InMemoryStreamingAdapter)


def test_mode_real_time_unconfigured_behavior():
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = SQLitePaperStorage(str(Path(tmp_dir) / "test_modes.db"))
        service = PaperTradingService(storage=storage)

        orig_key = settings.alpaca_api_key
        orig_sec = settings.alpaca_secret_key
        try:
            settings.alpaca_api_key = None
            settings.alpaca_secret_key = None

            cfg = {
                "mode": "REAL_TIME",
                "data_provider_type": "LIVE_PROVIDER",
                "live_provider": "alpaca",
                "symbols": ["AAPL"],
                "strategy": "TimeSeriesMomentum",
            }
            session = service.create_session(cfg)
            assert session.mode == SessionMode.REAL_TIME.value
            assert session.data_provider_type == "LIVE_PROVIDER"

            provider = service.providers[session.session_id]
            adapter = provider.adapter
            assert isinstance(adapter, AlpacaMarketDataAdapter)
            # Must be NOT_CONFIGURED when credentials are missing
            assert adapter.is_configured is False
            assert adapter.status.state == ConnectionState.NOT_CONFIGURED
            assert session.connection_state == ConnectionState.NOT_CONFIGURED.value
            # Strictly zero fake data fallback in REAL_TIME mode
            assert not isinstance(adapter, InMemoryStreamingAdapter)
        finally:
            settings.alpaca_api_key = orig_key
            settings.alpaca_secret_key = orig_sec
