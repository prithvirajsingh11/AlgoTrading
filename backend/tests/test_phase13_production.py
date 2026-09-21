"""Tests for Phase 13 Production Hardening, Observability, and Fault Tolerance."""

import os
import json
import tempfile
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.paper.service import PaperTradingService
from backend.app.paper.storage import SQLitePaperStorage
from backend.app.paper.session import PaperTradingSession, SessionStatus
from backend.app.ml.artifacts import MLModelArtifact
from backend.app.research.sweep import ParameterSweepRunner
from backend.app.research.config import ExperimentConfig, DatasetConfig, StrategyConfig
from backend.app.cli import demo_command


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    """Verifies liveness healthcheck endpoint."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] == "algotrade-backend"
    assert "timestamp" in data


def test_readiness_endpoint(client):
    """Verifies readiness probe checking filesystem storage and data paths."""
    res = client.get("/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("ready", "degraded")
    assert "checks" in data
    assert "raw_data_dir" in data["checks"]
    assert "paper_storage" in data["checks"]


def test_request_correlation_middleware(client):
    """Verifies X-Request-ID generation, preservation, and latency header."""
    # 1. Auto-generated request ID
    res1 = client.get("/health")
    assert "x-request-id" in res1.headers
    assert res1.headers["x-request-id"].startswith("req_")
    assert "x-response-time-ms" in res1.headers

    # 2. Client-provided request ID preserved
    custom_id = "test-client-correlation-987"
    res2 = client.get("/health", headers={"X-Request-ID": custom_id})
    assert res2.headers.get("x-request-id") == custom_id


def test_paper_trading_server_restart_crash_recovery():
    """Verifies that RUNNING sessions in storage are recovered as PAUSED after reboot."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_recovery.db"
        storage = SQLitePaperStorage(str(db_path))

        # Persist a session marked as RUNNING
        sess = PaperTradingSession(
            dataset_id="AAPL",
            symbols=["AAPL"],
            strategy="TimeSeriesMomentum",
            status=SessionStatus.RUNNING,
            total_bars=100,
            current_bar_index=25,
            current_equity=105000.0,
            cash=105000.0,
        )
        storage.save_session(sess)
        storage.close()

        # Simulate service restart
        storage_reboot = SQLitePaperStorage(str(db_path))
        svc = PaperTradingService(storage=storage_reboot)

        recovered = svc.get_session(sess.session_id)
        assert recovered is not None
        assert recovered.status == SessionStatus.PAUSED
        assert "interrupted by server restart" in recovered.error_message.lower()


def test_paper_trading_max_sessions_limit():
    """Verifies that exceeding max_paper_sessions raises ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_limits.db"
        storage = SQLitePaperStorage(str(db_path))
        svc = PaperTradingService(storage=storage)

        # Fill sessions up to max
        original_limit = settings.max_paper_sessions
        try:
            settings.max_paper_sessions = 2
            svc.create_session({"dataset_id": "AAPL_sample", "symbols": ["AAPL"]})
            svc.create_session({"dataset_id": "AAPL_sample", "symbols": ["AAPL"]})

            with pytest.raises(ValueError, match="Maximum active paper sessions limit reached"):
                svc.create_session({"dataset_id": "AAPL_sample", "symbols": ["AAPL"]})
        finally:
            settings.max_paper_sessions = original_limit


def test_model_artifact_integrity_validation():
    """Verifies cryptographic and structural integrity checking of ML model artifacts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        corrupt_path = Path(tmpdir) / "corrupt.json"

        # 1. Invalid JSON
        corrupt_path.write_text("{ malformed json", encoding="utf-8")
        with pytest.raises(ValueError, match="invalid JSON"):
            MLModelArtifact.load(str(corrupt_path))

        # 2. Missing required fields
        incomplete = {"model_json": "{}"}
        incomplete_path = Path(tmpdir) / "incomplete.json"
        incomplete_path.write_text(json.dumps(incomplete), encoding="utf-8")
        with pytest.raises(ValueError, match="missing required fields"):
            MLModelArtifact.load(str(incomplete_path))

        # 3. Mismatched schema hash
        mismatched = {
            "model_json": '{"learner":{}}',
            "feature_names": ["feat_1", "feat_2"],
            "feature_order": ["feat_1", "feat_2"],
            "feature_schema_hash": "invalid_hash_value_1234567890abcdef",
            "training_config": {},
            "label_config": {},
            "dataset_metadata": {},
            "training_period": ["2023-01-01", "2023-06-01"],
            "random_seed": 42,
        }
        mismatched_path = Path(tmpdir) / "mismatched.json"
        mismatched_path.write_text(json.dumps(mismatched), encoding="utf-8")
        with pytest.raises(ValueError, match="Artifact integrity violation"):
            MLModelArtifact.load(str(mismatched_path))


def test_sweep_parameter_limit_enforcement():
    """Verifies that oversized parameter sweeps are rejected before execution."""
    cfg = ExperimentConfig(
        dataset=DatasetConfig(dataset_id="AAPL_sample", symbols=["AAPL"]),
        strategy=StrategyConfig(name="MovingAverageCross"),
    )
    oversized_grid = {
        "fast_period": list(range(1, 40)),
        "slow_period": list(range(41, 80)),
    }  # 39 * 39 = 1521 combinations > 1000

    runner = ParameterSweepRunner()
    with pytest.raises(ValueError, match="exceed.*maximum allowed limit"):
        runner.run_sweep(cfg, oversized_grid)


def test_paper_trading_csv_exports(client):
    """Verifies CSV trade and equity export streaming endpoints."""
    # 1. Create a session via API
    create_res = client.post("/api/v1/paper/sessions", json={
        "dataset_id": "AAPL_sample",
        "symbols": ["AAPL"],
        "strategy": "TimeSeriesMomentum",
        "initial_capital": 100000.0,
    })
    assert create_res.status_code == 200
    sess_id = create_res.json()["session_id"]

    # 2. Advance 5 steps to populate state
    for _ in range(5):
        client.post(f"/api/v1/paper/sessions/{sess_id}/step")

    # 3. Export trades CSV
    trades_res = client.get(f"/api/v1/paper/sessions/{sess_id}/export/trades.csv")
    assert trades_res.status_code == 200
    assert "text/csv" in trades_res.headers.get("content-type", "")
    assert "trade_id,symbol,entry_time" in trades_res.text

    # 4. Export equity CSV
    equity_res = client.get(f"/api/v1/paper/sessions/{sess_id}/export/equity.csv")
    assert equity_res.status_code == 200
    assert "text/csv" in equity_res.headers.get("content-type", "")
    assert "timestamp,equity,cash" in equity_res.text


def test_cli_demo_execution():
    """Verifies that the CLI demo mode runs fully offline without errors."""
    exit_code = demo_command()
    assert exit_code == 0
