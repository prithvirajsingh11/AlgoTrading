"""
Test suite validating version consistency across all platform components for v1.0.0 release.
"""

import json
import subprocess
import sys
from pathlib import Path
from fastapi.testclient import TestClient

import backend.app
from backend.app.core.config import settings
from backend.app.main import app


def test_python_code_version():
    """Verify backend version constants match 1.0.0."""
    assert settings.version == "1.0.0"
    assert backend.app.__version__ == "1.0.0"
    assert app.version == "1.0.0"


def test_api_health_version():
    """Verify API /health and / endpoints return version 1.0.0."""
    client = TestClient(app)

    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    data = health_resp.json()
    assert data.get("version") == "1.0.0"

    root_resp = client.get("/")
    assert root_resp.status_code == 200
    root_data = root_resp.json()
    assert root_data.get("version") == "1.0.0"


def test_frontend_package_version():
    """Verify frontend/package.json version matches 1.0.0."""
    pkg_json_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "package.json"
    assert pkg_json_path.exists(), f"Frontend package.json missing at {pkg_json_path}"
    with open(pkg_json_path, "r", encoding="utf-8") as f:
        pkg = json.load(f)
    assert pkg.get("version") == "1.0.0"


def test_cli_version_flag():
    """Verify CLI --version flag returns 1.0.0 and exits cleanly."""
    result = subprocess.run(
        [sys.executable, "-m", "backend.app.cli", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "AlgoTrade v1.0.0" in result.stdout
