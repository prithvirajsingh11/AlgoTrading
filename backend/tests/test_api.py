from starlette.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "AlgoTrade" in data["project"]


def test_market_symbols_and_validation():
    response = client.get("/api/v1/market/symbols")
    assert response.status_code == 200
    symbols = response.json()
    assert "AAPL" in symbols

    val_res = client.get("/api/v1/market/validate/AAPL")
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert val_data["is_valid"] is True
    assert val_data["total_bars"] > 0


def test_list_strategies():
    response = client.get("/api/v1/strategies")
    assert response.status_code == 200
    strategies = response.json()
    ids = [s["id"] for s in strategies]
    assert "MovingAverageCross" in ids


def test_run_backtest_endpoint_success():
    payload = {
        "symbol": "AAPL",
        "strategy": "MovingAverageCross",
        "parameters": {"fast_period": 10, "slow_period": 30},
        "initial_capital": 100000.0,
        "commission_fixed": 1.0,
        "commission_percent": 0.0005,
        "slippage_bps": 5.0,
        "position_size_pct": 0.20,
    }
    response = client.post("/api/v1/backtest/run", json=payload)
    assert response.status_code == 200
    result = response.json()

    assert result["strategy_name"] == "MovingAverageCross"
    assert result["symbol"] == "AAPL"
    assert "metrics" in result
    assert result["metrics"]["initial_capital"] == 100000.0
    assert "equity_curve" in result
    assert len(result["equity_curve"]) > 0


def test_run_backtest_invalid_parameters():
    # fast >= slow must be rejected
    payload = {
        "symbol": "AAPL",
        "strategy": "MovingAverageCross",
        "parameters": {"fast_period": 50, "slow_period": 20},
    }
    response = client.post("/api/v1/backtest/run", json=payload)
    assert response.status_code == 422
