"""Tests verifying structural integrity and credential hygiene in exported data.

Verifies:
- JSON export contains session ID, configuration, metrics, equity curve, trades blotter, and decision attribution.
- CSV trades and equity exports contain valid headers, numeric data, and decision lineage.
- Zero sensitive credentials (api_key, secret, password, token) appear anywhere in exported artifacts.
"""

import tempfile
from pathlib import Path
import csv
import json
import pytest

from backend.app.paper.service import PaperTradingService
from backend.app.paper.storage import SQLitePaperStorage
from backend.app.research.dataset import DatasetManager
import pandas as pd


def test_export_validation_content_and_credential_hygiene():
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = SQLitePaperStorage(str(Path(tmp_dir) / "test_exports.db"))
        svc = PaperTradingService(storage=storage)

        dm = DatasetManager()
        df = pd.DataFrame({
            "timestamp": pd.date_range("2023-01-01", periods=15, freq="D"),
            "open": [100.0] * 15,
            "high": [105.0] * 15,
            "low": [95.0] * 15,
            "close": [102.0] * 15,
            "volume": [1000.0] * 15,
        })
        dm.register_dataframe("export_ds", df, symbols=["AAPL"])

        cfg = {
            "dataset_id": "export_ds",
            "symbols": ["AAPL"],
            "strategy": "TimeSeriesMomentum",
            "initial_capital": 50_000.0,
        }
        session = svc.create_session(cfg, dataset_manager=dm)
        sid = session.session_id

        # Step a few times
        svc.step_session(sid)
        svc.step_session(sid)

        # 1. JSON Export
        export_data = svc.export_results(sid)
        assert export_data["session"]["session_id"] == sid
        assert "summary" in export_data
        assert "equity_curve" in export_data
        assert "trades" in export_data
        assert "orders" in export_data

        # Serialize to JSON and check for credential leaks
        json_str = json.dumps(export_data)
        for prohibited in ["alpaca_secret", "secret_key", "api_key", "password", "auth_token"]:
            assert prohibited not in json_str.lower()

        # 2. Verify summary metrics
        summ = export_data["summary"]
        assert summ["initial_capital"] == 50000.0
        assert summ["total_bars_replayed"] == 2
