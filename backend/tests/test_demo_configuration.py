"""
Test suite validating configs/demo.json schema and completeness for Phase 17 release.
"""

import json
from pathlib import Path


def test_demo_configuration_exists_and_valid():
    """Verify configs/demo.json exists, parses, and has required sections."""
    root_dir = Path(__file__).resolve().parent.parent.parent
    demo_cfg_path = root_dir / "configs" / "demo.json"
    assert demo_cfg_path.exists(), "configs/demo.json must exist"

    with open(demo_cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    # Required top-level keys
    required_keys = [
        "version",
        "name",
        "demo_label",
        "dataset",
        "backtest",
        "comparative_strategies",
        "ml",
        "jev",
        "paper_trading",
        "export",
    ]
    for key in required_keys:
        assert key in cfg, f"Missing key '{key}' in configs/demo.json"

    assert cfg["version"] == "1.0.0"
    assert cfg["dataset"]["symbol"] == "AAPL"
    assert cfg["dataset"]["expected_bars"] >= 1000
    assert cfg["backtest"]["portfolio"]["initial_capital"] > 0
    assert len(cfg["comparative_strategies"]) >= 3
    assert cfg["paper_trading"]["rejection_order"]["excessive_quantity"] > 1000  # Deliberate oversized quantity
