"""Tests for Research API endpoints and Command Line Interface."""

import json
from starlette.testclient import TestClient
from backend.app.main import app
from backend.app.cli import main

client = TestClient(app)


def test_api_datasets_endpoints():
    # 1. List datasets
    resp = client.get("/api/v1/datasets")
    assert resp.status_code == 200
    datasets = resp.json()
    assert isinstance(datasets, list)
    assert any(d["dataset_id"] == "AAPL_sample" for d in datasets)

    # 2. Get dataset metadata
    resp_get = client.get("/api/v1/datasets/AAPL_sample")
    assert resp_get.status_code == 200
    meta = resp_get.json()
    assert meta["dataset_id"] == "AAPL_sample"
    assert meta["row_count"] > 0

    # 3. 404 for unknown dataset
    resp_404 = client.get("/api/v1/datasets/NON_EXISTENT")
    assert resp_404.status_code == 404

    # 4. Validate dataset
    resp_val = client.post("/api/v1/datasets/AAPL_sample/validate")
    assert resp_val.status_code == 200
    report = resp_val.json()
    assert report["valid"] is True
    assert report["rows"] > 0


def test_api_experiments_endpoints():
    config_payload = {
        "dataset": {"dataset_id": "AAPL_sample", "symbols": ["AAPL"]},
        "strategy": {"name": "MovingAverageCross", "parameters": {"fast_period": 5, "slow_period": 15}},
        "portfolio": {"initial_capital": 100000.0},
        "execution": {"commission_fixed": 1.0, "commission_percent": 0.0005, "slippage_bps": 5.0},
        "risk": {"position_sizing_method": "percent_equity", "position_size_pct": 0.20},
    }

    # 1. Create and run experiment
    resp_post = client.post("/api/v1/experiments", json=config_payload)
    assert resp_post.status_code == 200
    res = resp_post.json()
    exp_id = res["experiment_id"]
    assert exp_id.startswith("exp_")
    assert "metrics" in res
    assert len(res["equity_curve"]) > 0

    # 2. List experiments
    resp_list = client.get("/api/v1/experiments")
    assert resp_list.status_code == 200
    exp_list = resp_list.json()
    assert len(exp_list) >= 1
    assert any(e["experiment_id"] == exp_id for e in exp_list)

    # 3. Get specific experiment
    resp_get = client.get(f"/api/v1/experiments/{exp_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["experiment_id"] == exp_id

    # 4. Re-run experiment
    resp_rerun = client.post(f"/api/v1/experiments/{exp_id}/run")
    assert resp_rerun.status_code == 200
    assert resp_rerun.json()["experiment_id"] == exp_id


def test_cli_execution(tmp_path):
    # 1. list-datasets
    ret_list = main(["list-datasets"])
    assert ret_list == 0

    # 2. validate-dataset
    ret_val = main(["validate-dataset", "AAPL_sample"])
    assert ret_val == 0

    # 3. run-experiment from config file
    config_data = {
        "dataset": {"dataset_id": "AAPL_sample", "symbols": ["AAPL"]},
        "strategy": {"name": "MovingAverageCross", "parameters": {"fast_period": 5, "slow_period": 15}},
        "portfolio": {"initial_capital": 50000.0},
        "execution": {"commission_fixed": 1.0, "commission_percent": 0.0, "slippage_bps": 0.0},
        "risk": {"position_sizing_method": "percent_equity", "position_size_pct": 0.20},
    }
    cfg_file = tmp_path / "test_config.json"
    cfg_file.write_text(json.dumps(config_data), encoding="utf-8")

    ret_run = main(["run-experiment", str(cfg_file)])
    assert ret_run == 0

    # 4. sweep from config file
    grid_json = json.dumps({"fast_period": [5, 10]})
    ret_sweep = main(["sweep", str(cfg_file), "--grid", grid_json])
    assert ret_sweep == 0
