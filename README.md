# AlgoTrade — ML-Enhanced Algorithmic Trading & Backtesting Platform

A computer science portfolio project implementing a quantitative trading research, event-driven backtesting, and paper-trading platform.

> **Disclaimer:** This platform is strictly for research and simulated paper trading. It does not connect to real-money brokerage accounts or execute live monetary transactions.

---

## Key Features (Phases 1–8)

- **Quantitative Research Platform (Phase 8):**
  - **Dataset Management & Non-Throwing Validation:** `DatasetMetadata`, `DatasetManager`, and structured `ValidationReport` checking OHLC integrity, zero/negative prices, chronological order, duplicates, NaNs, and price spikes.
  - **Declarative Experiment Configuration & Canonical Hashing:** Fully serializable `ExperimentConfig` with deterministic SHA-256 hashing across data, strategy, risk, execution, and walk-forward parameters.
  - **Deterministic Reproducibility:** 100% bit-for-bit repeatable backtest and walk-forward runs with identical metrics, equity curves, drawdown curves, and trade records.
  - **Overfitting Safeguards & Chronological Splitting:** Non-overlapping chronological train/validation/test partitioning with test-set quarantine and zero temporal shuffling.
  - **Grid Parameter Sweeps & Leaderboards:** `ParameterSweepRunner` across discrete parameter combinations with multi-metric sorting and train/test evaluation.
  - **Artifact Persistence:** Plug-and-play storage interface with `SQLiteExperimentStorage` recording experiments, configs, metrics, and equity series.
  - **Unified CLI & REST API:** Full CLI (`python -m backend.app.cli`) and FastAPI endpoints (`/api/v1/datasets`, `/api/v1/experiments`).
- **Event-Driven Backtest Engine:** Chronological bar-by-bar execution model with zero future lookahead bias.
- **Production-Quality Trading Strategies:**
  - `MovingAverageCrossStrategy`: Dual fast/slow moving average trend following.
  - `TimeSeriesMomentumStrategy`: Configurable lookback return momentum and entry/exit thresholds.
  - `MeanReversionStrategy`: Rolling mean, standard deviation, and dynamic z-score ($z = \frac{Close - \mu}{\sigma}$).
  - `PairsTradingStrategy`: Statistical arbitrage with cointegrated spread, dynamic OLS hedge ratio $\beta = \frac{Cov(P_1, P_2)}{Var(P_2)}$, and spread z-scores.
- **Advanced Position Sizing & Stop-Loss Protection:**
  - `RiskBasedPositionSizer`: Formulated by account equity, stop-loss price, and risk percentage ($\lfloor \frac{\text{Equity} \times \text{Risk\%}}{|\text{Entry} - \text{Stop}|} \rfloor$).
  - `OrderType.STOP_LOSS` in simulated broker and proactive position-level stop monitoring in `RiskManager`.
- **Walk-Forward Out-Of-Sample Backtesting:**
  - Strictly chronological sliding windows ($Train \to Test \to Shift$) with zero data leakage or lookahead.
  - Generates per-window out-of-sample metrics and combined out-of-sample performance curves.
- **Multi-Strategy Comparison Service:**
  - Benchmarks multiple strategies against the same dataset across 9 standardized metrics.
- **Complete Financial Accounting:**
  - Real-time cash balance tracking, positions with weighted average entry prices, realized/unrealized P&L reconciliation, mark-to-market portfolio equity.
- **Automated Verification:**
  - 94 unit and integration tests covering all critical components with 100% pass rate.

---

## System Architecture

```
                                  [ Historical OHLCV Data (CSV) ]
                                                │
                                                ▼
                                      [ Data Validator & Cleaner ]
                                                │
                                                ▼
     ┌────────────────────────────────── [ Backtest Engine ] ──────────────────────────────────┐
     │                                                                                         │
     │   For each bar t (strictly chronological):                                              │
     │   1. SimulatedBroker: Check & fill pending limit orders                                 │
     │   2. Portfolio: Mark-to-market at current bar close                                     │
     │   3. BaseStrategy: Generate signal using historical slice [0..t] (No Lookahead)         │
     │   4. BasePositionSizer: Calculate order size based on available equity                  │
     │   5. RiskManager: Check cash sufficiency, concentration limit & drawdown circuit breaker│
     │   6. SimulatedBroker: Execute market orders with slippage & commissions                 │
     │   7. Portfolio: Update cash, positions, realized/unrealized P&L, record trades          │
     │                                                                                         │
     └──────────────────────────────────────────┬──────────────────────────────────────────────┘
                                                │
                                                ▼
                                   [ Performance Metrics Engine ]
                             (Sharpe, Sortino, Max Drawdown, Win Rate, CAGR)
                                                │
                                                ▼
                                    [ Structured BacktestResult ]
                                (Frontend-ready JSON API Response)
```

---

## Directory Structure

```
AlgoTrading/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes_market.py       # Datasets & symbol endpoints
│   │   │   ├── routes_strategy.py     # Strategy registry & parameter schemas
│   │   │   ├── routes_backtest.py     # Backtest execution endpoint
│   │   │   ├── routes_portfolio.py    # Portfolio inspection endpoint
│   │   │   ├── routes_paper.py        # Paper trading session stubs
│   │   │   ├── routes_datasets.py     # Research dataset metadata & validation endpoints
│   │   │   └── routes_experiments.py  # Research experiment execution, listing, & re-run
│   │   ├── research/                  # Quantitative research & reproducibility engine
│   │   │   ├── dataset.py             # DatasetMetadata & DatasetManager abstraction
│   │   │   ├── validator.py           # DatasetValidator & structured ValidationReport
│   │   │   ├── config.py              # ExperimentConfig & canonical SHA-256 hash
│   │   │   ├── result.py              # JSON-serializable ExperimentResult & drawdown curve
│   │   │   ├── splits.py              # Chronological train/val/test splits & quarantine
│   │   │   ├── storage.py             # BaseExperimentStorage & SQLite persistence
│   │   │   ├── runner.py              # ExperimentRunner (backtest & walk-forward)
│   │   │   └── sweep.py               # ParameterSweepRunner & multi-metric ranking
│   │   ├── cli.py                     # Quantitative research CLI tool
│   │   ├── core/
│   │   │   ├── config.py              # Pydantic configuration & env loading
│   │   │   └── database.py            # Database session & engine setup
│   │   ├── data/
│   │   │   ├── loader.py              # CSV loader & OHLCV bar dataclass
│   │   │   ├── cleaner.py             # Data integrity & chronology validation
│   │   │   └── features.py            # Technical indicators (SMA, EMA, Volatility)
│   │   ├── strategies/
│   │   │   ├── base.py                # BaseStrategy abstract class
│   │   │   ├── momentum.py            # TimeSeriesMomentum & MovingAverageCross
│   │   │   ├── mean_reversion.py      # Statistical MeanReversionStrategy
│   │   │   ├── pairs_trading.py       # True multi-asset PairsTradingStrategy
│   │   │   └── ml_strategy.py         # ML strategy integration stub
│   │   ├── backtesting/
│   │   │   ├── engine.py              # Chronological event-driven engine
│   │   │   ├── broker.py              # Simulated broker (slippage, fees, stops, limits)
│   │   │   ├── orders.py              # Order, Signal, Trade data models
│   │   │   └── portfolio.py           # Multi-asset long/short position accounting
│   │   ├── risk/
│   │   │   ├── position_sizing.py     # Fixed, % Equity, and Risk-based sizers
│   │   │   ├── risk_manager.py        # Risk checks, stops & circuit breaker
│   │   │   └── metrics.py             # Quantitative performance calculations
│   │   ├── ml/
│   │   │   ├── features.py            # ML feature extraction stubs
│   │   │   ├── train.py               # Model training stubs
│   │   │   ├── evaluate.py            # Model evaluation stubs
│   │   │   └── model.py               # ML model wrapper stub
│   │   └── main.py                    # FastAPI application entry point
│   ├── tests/                         # Comprehensive pytest test suite (94 passing tests)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                          # React + TypeScript scaffold
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── charts/
│   │   └── services/
│   └── package.json
├── data/
│   ├── raw/                           # Historical OHLCV datasets (e.g. AAPL_sample.csv)
│   ├── processed/
│   └── models/
├── notebooks/                         # Quantitative research & exploratory notebooks
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- (Optional) Docker and Docker Compose

### Local Installation

1. Clone repository and create a virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .\.venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```

3. Configure environment variables:
   ```bash
   cp .env.example .env
   ```

### Running the Backend

Start the FastAPI application using `uvicorn`:

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive API documentation will be available at:
- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`
- **Health Check:** `http://127.0.0.1:8000/health`

### Running the Automated Tests

Execute the full automated test suite with verbose output:

```bash
pytest backend/tests -v
```

All 94 tests verify:
- Order lifecycle, validation, and multi-asset position accounting
- Simulated broker execution, slippage, commissions, stops, and limits
- Intrabar stop-loss execution, gap policy, and ambiguity resolution
- True multi-asset pairs trading, synchronized snapshots, and cointegration
- Pre-trade risk controls, position sizing, and circuit breakers
- Trend-following, momentum, mean-reversion, and statistical arbitrage strategies
- Quantitative performance metrics (Sharpe, Sortino, Drawdown, Calmar, Profit Factor)
- Event-driven engine chronology, walk-forward out-of-sample slices, and zero lookahead
- Dataset management, non-throwing validation reports, and chronological partitioning
- Declarative experiment serialization, canonical hashing, and SQLite persistence
- Mandatory bit-for-bit reproducibility regression (identical metrics, curves, trades)
- Grid parameter sweep execution, overfitting safeguards, and multi-metric ranking
- FastAPI REST endpoints and research CLI commands

---

## Running a Backtest via API

You can execute a backtest against the included local historical dataset (`AAPL_sample.csv`) via `curl` or any HTTP client:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/backtest/run" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "strategy": "MovingAverageCross",
    "parameters": {
      "fast_period": 10,
      "slow_period": 30
    },
    "initial_capital": 100000.0,
    "commission_fixed": 1.0,
    "commission_percent": 0.0005,
    "slippage_bps": 5.0,
    "position_size_pct": 0.20
  }'
```

### Sample Response

```json
{
  "strategy_name": "MovingAverageCross",
  "symbol": "AAPL",
  "parameters": {
    "fast_period": 10,
    "slow_period": 30
  },
  "metrics": {
    "initial_capital": 100000.0,
    "final_equity": 108420.50,
    "total_return": 0.0842,
    "annualized_return": 0.0820,
    "volatility": 0.1245,
    "sharpe_ratio": 0.4980,
    "sortino_ratio": 0.6510,
    "maximum_drawdown": 0.0620,
    "win_rate": 0.6667,
    "number_of_trades": 6,
    "profit_factor": 2.34
  },
  "equity_curve": [ ... ],
  "trades": [ ... ]
}
```

---

## Execution Model & Limitations

### 1. Discrete OHLCV Simulation & Gap Policy
Backtesting executes over discrete chronological bars ($\text{Open}, \text{High}, \text{Low}, \text{Close}$). Because sub-bar price trajectories are unobservable without tick data, simulated order execution adheres to a deterministic, conservative policy:
- **Long Stop-Loss (`SELL`):**
  - **Gap-Down:** If $\text{Open} \le \text{Stop Price}$, the market opened below the protective threshold. The order fills at $\text{Open} - \text{Slippage}$ (penalizing the trade for the gap).
  - **Intrabar Breach:** If $\text{Open} > \text{Stop Price}$ and $\text{Low} \le \text{Stop Price}$, price traded through the stop during the bar. The order fills at $\text{Stop Price} - \text{Slippage}$.
- **Short Stop-Loss (`BUY` to Cover):**
  - **Gap-Up:** If $\text{Open} \ge \text{Stop Price}$, the market opened above the stop threshold. The order fills at $\text{Open} + \text{Slippage}$.
  - **Intrabar Breach:** If $\text{Open} < \text{Stop Price}$ and $\text{High} \ge \text{Stop Price}$, price traded through the stop during the bar. The order fills at $\text{Stop Price} + \text{Slippage}$.

### 2. Intrabar Ambiguity Resolution
When both a stop-loss and a limit order (e.g. take-profit target) are active within the same bar and both extreme price levels are breached ($\text{High} \ge \text{Limit}$ and $\text{Low} \le \text{Stop}$):
- The platform enforces a **pessimistic risk-first execution policy**: the stop-loss order is evaluated and filled first.
- Conflicting limit orders for that position are automatically cancelled to avoid double execution or unintended short exposure.

### 3. Order Lifecycle & Active Stop Tracking
- Orders transition through explicit states: $\text{PENDING} \to \text{TRIGGERED} \to \text{FILLED}$ (or $\text{CANCELLED}$).
- When a position is closed (either by normal strategy exit or protective stop-loss), all active stop-loss and protective orders for that symbol are cleaned up immediately to prevent orphaned fills.

### 4. True Multi-Asset Pairs Trading & Lookahead Prevention
- **`MarketSnapshot` Feed:** Encapsulates synchronized multi-asset observations at timestamp $t$.
- **Timestamp Intersection:** Multi-asset datasets are strictly synchronized by their common trading timestamps. Any dataset containing duplicate timestamps, missing values, unsorted order, or disjoint ranges is rejected.
- **Dynamic Hedge Ratio:** $\beta_t = \frac{\text{Cov}(P_A, P_B)}{\text{Var}(P_B)}$ is estimated strictly using observations up to $t$.
- **Two-Leg Execution:** Long spread buys Asset A and sells Asset B ($Q_B = Q_A \cdot \beta_t$); short spread sells Asset A and buys Asset B; exit signals close both legs simultaneously.
- **Short Accounting:** Full liability tracking where short market value is negative, cash is credited upon short sale, and buy-to-cover realizes $(\text{Entry} - \text{Fill}) \times Q - \text{Fees}$.

---

## Quantitative Research Platform (Phase 8)

AlgoTrade features a reproducible quantitative research environment designed to eliminate survivorship, lookahead, and data-mining biases from strategy formulation to evaluation.

### Research Workflow

The quantitative workflow enforces a strict linear pipeline from raw historical inputs to persistent experiment artifacts:

```
[ Dataset Registry ] ──▶ [ DatasetValidator ] ──▶ [ Chronological Split ]
                                                          │ (Train / Val / Test Quarantine)
                                                          ▼
[ Experiment Storage ] ◀── [ ExperimentRunner ] ──▶ [ ExperimentConfig (SHA-256) ]
                                  │
                                  ├──▶ Standard Event-Driven Engine
                                  └──▶ Walk-Forward Evaluator
```

1. **Dataset Ingestion & Registration:** Files in `data/raw` (or registered in-memory dataframes) are registered with explicit `DatasetMetadata` (symbol, timeframe, bar count, date range, column listing).
2. **Structural Validation:** `DatasetValidator` produces a non-throwing `ValidationReport` checking required columns (`timestamp`, `open`, `high`, `low`, `close`, `volume`), chronological ordering, duplicate timestamps, valid OHLC boundaries ($High \ge \max(Open, Close)$ and $Low \le \min(Open, Close)$), positive prices ($>0$), non-negative volumes ($\ge 0$), NaNs, and single-bar price jump warnings ($>50\%$).
3. **Declarative Configuration:** All execution parameters—dataset, strategy, risk, execution slippage/fees, and walk-forward windows—are defined via a single immutable `ExperimentConfig`.
4. **Canonical Hashing:** A deterministic SHA-256 hash is computed over canonical JSON representation with sorted keys and normalized floats. Re-running the exact same configuration yields an identical hash and reproduces results with bit-for-bit fidelity.
5. **Execution & Quarantine:** Runs can execute standard backtests or walk-forward out-of-sample evaluations. In walk-forward or chronological splits, test data is quarantined until model/strategy parameters are frozen.
6. **Artifact Storage:** `SQLiteExperimentStorage` records complete experiment records, configs, metrics, equity curves, drawdown curves, and trade records into SQLite.

### Reproducibility Guarantee

Quantitative research requires deterministic reproducibility. AlgoTrade guarantees that executing an experiment twice under the same `ExperimentConfig` yields:
- Identical configuration SHA-256 hash and experiment ID.
- Identical float metrics (Sharpe ratio, CAGR, max drawdown, win rate, etc.).
- Identical bar-by-bar portfolio equity curve.
- Identical bar-by-bar drawdown percentage curve.
- Identical executed trade records, quantities, fill prices, and commissions.

### Avoiding Overfitting

Overfitting and data snooping are primary causes of algorithmic failure in production. AlgoTrade enforces systematic safeguards:
1. **Strict Chronological Splitting (`chronological_split`):** Data is strictly partitioned chronologically into `[train_start, train_end]`, `[val_start, val_end]`, and `[test_start, test_end]` with non-overlapping temporal windows ($T_{\text{train}} < T_{\text{val}} < T_{\text{test}}$). Temporal random shuffling is strictly prohibited.
2. **Out-of-Sample Test Quarantine:** Strategy parameters and hedge ratios must only be fitted on training/validation periods. Test-set evaluation occurs only once on unseen future data.
3. **Walk-Forward Validation:** Evaluates strategies across rolling out-of-sample segments ($Train \to Test \to Shift$) to verify performance stability across differing market regimes.
4. **Parameter Sweep Leaderboards:** `ParameterSweepRunner` reports both in-sample training and out-of-sample test metrics side-by-side, penalizing strategies that exhibit sharp drops between in-sample and out-of-sample Sharpe ratios.

### Sample Experiment Configuration

```json
{
  "name": "AAPL_Momentum_Research",
  "description": "Evaluate 20-bar momentum with 2% risk sizing",
  "dataset": {
    "dataset_id": "AAPL_sample",
    "symbol": "AAPL",
    "timeframe": "1d",
    "train_ratio": 0.7,
    "val_ratio": 0.15,
    "test_ratio": 0.15
  },
  "strategy": {
    "strategy_name": "TimeSeriesMomentum",
    "parameters": {
      "lookback_period": 20,
      "threshold": 0.01
    }
  },
  "risk": {
    "initial_capital": 100000.0,
    "sizer_type": "risk_based",
    "risk_percent": 0.02,
    "stop_loss_pct": 0.03,
    "max_drawdown_limit": 0.15
  },
  "execution": {
    "commission_fixed": 1.0,
    "commission_percent": 0.0005,
    "slippage_bps": 5.0
  },
  "random_seed": 42
}
```

### Command-Line Interface (CLI)

The platform provides a CLI module (`backend.app.cli`) for automated research workflows:

```bash
# 1. List registered datasets
python -m backend.app.cli list-datasets

# 2. Validate dataset integrity
python -m backend.app.cli validate-dataset --dataset AAPL_sample

# 3. Run a reproducible experiment from config file
python -m backend.app.cli run-experiment --config config.json --db experiments.db

# 4. Execute a parameter sweep
python -m backend.app.cli sweep --config-template config.json --param-grid '{"strategy.parameters.lookback_period": [10, 20, 30]}' --sort-by sharpe_ratio
```

### Research REST API Endpoints

- `GET /api/v1/datasets`: List all discovered datasets and summary metadata.
- `GET /api/v1/datasets/{id}`: Detailed dataset metadata (timeframe, row count, date ranges).
- `POST /api/v1/datasets/{id}/validate`: Run structured dataset integrity audit.
- `POST /api/v1/experiments`: Run and persist a reproducible experiment.
- `GET /api/v1/experiments`: List stored experiments with pagination and tag filtering.
- `GET /api/v1/experiments/{id}`: Fetch complete experiment result with equity/drawdown curves.
- `POST /api/v1/experiments/{id}/rerun`: Rerun experiment from saved configuration and verify reproducibility.

---

## Roadmap

 - [x] **Phase 1:** Project foundation and modular architecture.
 - [x] **Phase 2:** Historical market data loader, cleaning, and validation.
 - [x] **Phase 3:** Event-driven backtesting engine, simulated broker, and portfolio accounting.
 - [x] **Phase 4:** Moving Average Crossover momentum strategy.
 - [x] **Phase 5:** Quantitative performance metrics (Sharpe, Sortino, Max Drawdown).
 - [x] **Phase 6:** Automated test suite (35 passing tests).
 - [x] **Phase 7:** Strategy expansion (Momentum, Mean Reversion, Pairs Trading), Risk Sizing, Stop-Loss, Walk-Forward backtester, and Strategy Comparator (51 passing tests).
 - [x] **Phase 7.1:** True Multi-Asset Pairs Trading & Realistic Stop-Loss Execution (70 passing tests).
 - [x] **Phase 8:** Quantitative Research Platform & Reproducibility (94 passing tests).
 - [ ] **Phase 9:** Machine Learning feature pipeline & XGBoost predictive model.
 - [ ] **Phase 10:** Real-time paper-trading session daemon.
 - [ ] **Phase 11:** React + TypeScript interactive analytics dashboard.