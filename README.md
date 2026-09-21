# AlgoTrade — ML-Enhanced Algorithmic Trading & Backtesting Platform

A computer science portfolio project implementing a quantitative trading research, event-driven backtesting, and paper-trading platform.

> **Disclaimer:** This platform is strictly for research and simulated paper trading. It does not connect to real-money brokerage accounts or execute live monetary transactions.

---

## Key Features (Phases 1–8.1)

- **Optional Jev AI Decision Layer (Phase 8.1):**
  - **TypeSafe SystemOne Integration:** Machine-native structured decision questions (`POST https://api.typesafe.ai/v1/systemone`) evaluating compact market context.
  - **Advisory Architecture:** Jev advises and filters strategy signals; deterministic Risk Manager, Broker, and Portfolio remain authoritative.
  - **Zero Lookahead Context Builder:** Strictly derives single-asset and pairs-trading indicators (SMA, EMA, RSI, MACD, ATR, volatility, hedge ratio, spread z-score) on historical slice $0..t$.
  - **Deterministic Decision Caching:** SHA-256 keyed cache (`config_hash + model + timestamp + symbol + context_hash`) enabling exact offline replay without repeat API calls (`CACHED_JEV` vs `LIVE_JEV`).
  - **Fail-Safe Fallback:** Network timeouts, HTTP errors, and confidence below `min_confidence` (default 0.60) automatically fail safe to `NO_ACTION` without order submission.
- **Quantitative Research Platform (Phase 8):**
  - **Dataset Management & Non-Throwing Validation:** `DatasetMetadata`, `DatasetManager`, and structured `ValidationReport` checking OHLC integrity, zero/negative prices, chronological order, duplicates, NaNs, and price spikes.
  - **Declarative Experiment Configuration & Canonical Hashing:** Fully serializable `ExperimentConfig` with deterministic SHA-256 hashing across data, strategy, risk, execution, and walk-forward parameters.
  - **Deterministic Reproducibility:** 100% bit-for-bit repeatable backtest and walk-forward runs with identical metrics, equity curves, drawdown curves, and trade records.
  - **Overfitting Safeguards & Chronological Splitting:** Non-overlapping chronological train/validation/test partitioning with test-set quarantine and zero temporal shuffling.
  - **Grid Parameter Sweeps & Leaderboards:** `ParameterSweepRunner` across discrete parameter combinations with multi-metric sorting and train/test evaluation.
  - **Artifact Persistence:** Plug-and-play storage interface with `SQLiteExperimentStorage` recording experiments, configs, metrics, and equity series.
  - **Unified CLI & REST API:** Full CLI (`python -m backend.app.cli`) and FastAPI endpoints (`/api/v1/datasets`, `/api/v1/experiments`, `/api/v1/ai/jev`).
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
  - 112 automated unit and integration tests covering all critical components with 100% pass rate.

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
│   │   │   ├── routes_experiments.py  # Research experiment execution, listing, & re-run
│   │   │   └── routes_ai.py           # Jev AI decision engine status & evaluation
│   │   ├── ai/                        # Optional AI decision layer (Phase 8.1)
│   │   │   ├── jev_client.py          # TypeSafe SystemOne API client
│   │   │   ├── jev_schema.py          # Decision schemas (BUY, SELL, HOLD, NO_ACTION)
│   │   │   ├── jev_context.py         # Zero-lookahead market context builder
│   │   │   └── jev_decision.py        # DecisionProvider, caching & test mocks
│   │   ├── research/                  # Quantitative research & reproducibility engine
│   │   │   ├── dataset.py             # DatasetMetadata & DatasetManager abstraction
│   │   │   ├── validator.py           # DatasetValidator & structured ValidationReport
│   │   │   ├── config.py              # ExperimentConfig, JevConfig & canonical hashing
│   │   │   ├── result.py              # JSON-serializable ExperimentResult & drawdown curve
│   │   │   ├── splits.py              # Chronological train/val/test splits & quarantine
│   │   │   ├── storage.py             # BaseExperimentStorage & SQLite persistence
│   │   │   ├── runner.py              # ExperimentRunner (backtest & walk-forward)
│   │   │   └── sweep.py               # ParameterSweepRunner & multi-metric ranking
│   │   ├── cli.py                     # Quantitative research & AI CLI tool
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
│   │   │   ├── engine.py              # Chronological event-driven engine + AI decision hook
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
│   ├── tests/                         # Comprehensive pytest test suite (112 passing tests)
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

# 5. Check Jev AI decision layer status
python -m backend.app.cli jev-status

# 6. Evaluate market context with Jev AI
python -m backend.app.cli jev-evaluate '{"symbol": "AAPL", "price": 175.50, "rsi_14": 42.0, "timestamp": "2023-05-01"}'
```

### Research & AI REST API Endpoints

- `GET /api/v1/datasets`: List all discovered datasets and summary metadata.
- `GET /api/v1/datasets/{id}`: Detailed dataset metadata (timeframe, row count, date ranges).
- `POST /api/v1/datasets/{id}/validate`: Run structured dataset integrity audit.
- `POST /api/v1/experiments`: Run and persist a reproducible experiment.
- `GET /api/v1/experiments`: List stored experiments with pagination and tag filtering.
- `GET /api/v1/experiments/{id}`: Fetch complete experiment result with equity/drawdown curves.
- `POST /api/v1/experiments/{id}/rerun`: Rerun experiment from saved configuration and verify reproducibility.
- `GET /api/v1/ai/jev/status`: Operational status, configured model, and provider health.
- `POST /api/v1/ai/jev/evaluate`: Evaluate structured market context through active decision provider.

---

## Jev AI Decision Layer (Phase 8.1)

AlgoTrade integrates **Jev** (via TypeSafe's SystemOne API) as an optional, modular AI decision layer. Jev evaluates machine-readable market context and issues structured, probabilistic decisions (`BUY`, `SELL`, `HOLD`, `NO_ACTION`) to confirm or suppress signals generated by underlying strategies.

### Target Architecture & Decision Flow

```
Market Data
    │
    ▼
Feature Engine (SMA, EMA, RSI, MACD, ATR, Volatility)
    │
    ▼
Existing Strategies (Momentum, Mean Reversion, Pairs Trading)
    │
    ▼
Strategy Signals + Historical Market Context
    │
    ▼
┌───────────────────────────────────────────────┐
│        OPTIONAL JEV DECISION ENGINE           │
│  (TypeSafe SystemOne 'choice' API Evaluation) │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
             Structured AI Decision
       (BUY / SELL / HOLD / NO_ACTION)
                        │
                        ▼
                   Risk Manager
      (Position limits, stops, cash & exposure)
                        │
                        ▼
                   Order Engine
                        │
                        ▼
                 Simulated Broker
            (Slippage, fees, stops, limits)
                        │
                        ▼
                   Portfolio
        (Cash, positions, P&L reconciliation)
```

### Authoritative Architecture & Safety Controls

1. **Advisory Role Only:** Jev produces recommendations; it **never** directly submits exchange or broker orders.
2. **Authoritative Risk Manager:** All orders must satisfy cash availability, position concentration limits ($\le 50\%$), and drawdown circuit breakers ($\le 30\%$). Jev cannot bypass protective stop-losses or risk limits.
3. **Structured Decisions:** Free-form text prompts are prohibited. Requests follow TypeSafe's `choice` primitive:
   ```json
   {
     "model": "jev-latest",
     "state": "{ ...compact market context... }",
     "questions": {
       "trading_action": {
         "type": "choice",
         "instructions": "Given the supplied market state, which trading action is most appropriate?",
         "criteria": {
           "BUY": "Conditions favor taking or increasing a long exposure",
           "SELL": "Conditions favor reducing or taking short exposure",
           "HOLD": "Conditions do not justify changing exposure"
         }
       }
     }
   }
   ```
4. **Confidence Thresholding:** Configurable via `min_confidence` (default 0.60). If model confidence is below threshold, the decision is demoted to `HOLD` and signal execution is suppressed.
5. **Fail-Safe Fallback:** On API timeouts, network errors, HTTP 500s, or invalid JSON, Jev automatically falls back to `NO_ACTION` and logs the incident. No orders are executed.
6. **Zero Future Lookahead Guarantee:** The market context builder derives all indicators (SMA, EMA, RSI, MACD, ATR, Volatility, Hedge Ratio, Spread) strictly on the chronological slice $0..t$. Future prices, returns, indicators, and backtest outcomes are strictly excluded.
7. **Deterministic Decision Cache:** Replaying experiments utilizes a persistent SHA-256 cache keyed by `(config_hash, model, timestamp, symbol, context_hash)`. Cached runs record `source: "CACHED_JEV"` and live queries record `source: "LIVE_JEV"`, enabling bit-for-bit reproducibility without recurring API costs.

### Jev vs Traditional Strategies

| Dimension | Traditional Strategies (Momentum, Mean Reversion) | Jev AI Decision Layer |
| :--- | :--- | :--- |
| **Role** | Core quantitative hypothesis & signal generation | Secondary probabilistic confirmation / filtering |
| **Logic** | Deterministic mathematical formulas | Multi-feature probabilistic classification (`choice`) |
| **Execution** | Feeds directly into Risk Manager | Filters signals before Risk Manager |
| **Profitability** | Backtested on historical data | Evaluated as an advisory layer; not proof of alpha |
| **Availability** | Offline / Always available | Optional; fails safe to `NO_ACTION` if offline |

### Local Setup & Configuration

Jev is **disabled by default**. To configure and enable Jev:

1. Add your TypeSafe API key to `.env`:
   ```bash
   JEV_ENABLED=true
   JEV_API_KEY=your_typesafe_api_key_here
   JEV_MODEL=jev-latest
   JEV_TIMEOUT_SECONDS=5.0
   JEV_MIN_CONFIDENCE=0.60
   ```
   > **Security Note:** `JEV_API_KEY` is loaded server-side only. It is never sent to frontend clients and is never serialized into experiment result artifacts.

2. Verify operational status:
   ```bash
   python -m backend.app.cli jev-status
   ```

3. Evaluate a market context:
   ```bash
   python -m backend.app.cli jev-evaluate '{"symbol": "AAPL", "price": 175.50, "rsi_14": 42.0, "timestamp": "2023-05-01"}'
   ```

---

## Machine Learning Research (Phase 9)

AlgoTrade includes an end-to-end supervised machine learning research pipeline powered by **XGBoost**. The ML module is decoupled from execution and broker systems, enforces strict zero-lookahead feature calculation, supports time-aware chronological evaluation, and emits versioned model artifacts with strict schema validation.

### Architecture & Pipeline Flow

```
Market Data (OHLCV)
       │
       ▼
Feature Pipeline (Strictly 0..t: Returns, SMA/EMA Distances, RSI, MACD, ATR, Volatility, Volume)
       │
       ▼
Target / Label Generator (Supervised ground truth: close[t + N] / close[t] - 1 > threshold)
       │
       ▼
Supervised Alignment (Trim warmup and horizon NaNs, preserve temporal order)
       │
       ▼
Time-Series Splitter (Train [0..i1) -> Validation [i1..i2) -> Test [i2..N); Scaler fit ONLY on Train)
       │
       ▼
XGBoost Classifier (Deterministic training with fixed seed, early stopping on validation)
       │
       ▼
Model Calibration (Platt Sigmoid / Isotonic Regression / Brier Score assessment)
       │
       ▼
Versioned MLModelArtifact (Model JSON, Feature Order, Schema Hash, Scaler State)
       │
       ▼
Inference / MLPredictor (Outputs structured MLPrediction with P(up) and P(down))
       │
       ▼
MLStrategy (BaseStrategy implementation: P(up) >= buy_thresh -> BUY, P(up) <= sell_thresh -> SELL)
       │
       ▼
Authoritative RiskManager (Position sizing, 50% concentration limit, 30% drawdown breaker)
       │
       ▼
Simulated Broker -> Portfolio
```

### ML Data Leakage Prevention

Financial time-series data is uniquely vulnerable to catastrophic data leakage. AlgoTrade implements 5 verifiable data leakage safeguards:

1. **Information Barrier:** Future price information ($Close_{t+N}$) is permitted **strictly** for generating supervised training labels ($y$). Future prices and returns are strictly barred from entering the feature matrix ($X$).
2. **Zero-Lookahead Feature Invariant:** Every indicator feature at timestamp $t$ is calculated exclusively from historical bars in the closed interval $[0 \dots t]$. Mutating future prices at $t+1$ produces zero change in feature values at or before $t$.
3. **Chronological Splitting:** Random train/test splits and standard K-fold cross validation are forbidden. Partitions strictly follow chronological order: $T_{\text{train}} < T_{\text{val}} < T_{\text{test}}$.
4. **Out-of-Sample Test Isolation:** The final test set is quarantined during feature scaling and model selection. Feature scalers (e.g., `StandardScaler`, `MinMaxScaler`) are fit **only** on the training partition ($X_{\text{train}}$) and applied downstream.
5. **Walk-Forward ML Isolation:** In walk-forward ML evaluation, models are trained on past data, frozen, and evaluated on out-of-sample test windows without retraining on future test data.

### Model Evaluation: Classification vs Trading Performance

AlgoTrade explicitly decouples **Classification Metrics** from **Trading Metrics**:

- **Classification Metrics:** Accuracy, Precision, Recall, F1 Score, ROC-AUC, Log-Loss, and Brier Score measure statistical discrimination on the discrete prediction problem ($P(\text{return} > \text{threshold})$).
- **Trading Metrics:** Total Return, CAGR, Sharpe Ratio, Sortino Ratio, Maximum Drawdown, Profit Factor, and Win Rate measure real-world portfolio outcomes after accounting for execution costs, slippage, trade frequency, and holding duration.

> [!WARNING]
> **The Accuracy Fallacy:** High classification accuracy does not guarantee profitable trading. A model with 65% directional accuracy can lose capital if its losing trades are larger than its winning trades, if transaction costs and bid-ask slippage erode small gains, or if severe drawdowns trigger risk-management liquidations. Conversely, a strategy with 40% accuracy can be highly profitable if its winners significantly outperform its losers (positive asymmetry).

### Strategy Comparison: Traditional vs XGBoost vs Jev

AlgoTrade provides a unified interface to compare quantitative strategies across three distinct paradigms:

| Dimension | Traditional Rule-Based (Momentum, Mean Reversion) | Supervised ML (XGBoost) | Advisory AI (Jev Decision Layer) |
| :--- | :--- | :--- | :--- |
| **Paradigm** | Fixed mathematical hypotheses | Supervised non-linear pattern learning | Multi-criteria probabilistic evaluation |
| **Inputs** | Indicator formulas (e.g., MA cross, Z-score) | 19 zero-lookahead engineered technical features | Compact structured market state snapshot |
| **Output** | Deterministic boolean signal | Directional probability distribution $P(\text{up})$ | Structured decision (`BUY`, `SELL`, `HOLD`, `NO_ACTION`) |
| **Role** | Primary signal generator | Primary signal generator (`MLStrategy`) | Secondary filter / signal confirmation |
| **Dependencies** | Offline / Zero external dependencies | Offline / Local XGBoost library | Remote HTTP API (TypeSafe SystemOne) |
| **Cost** | Zero | Local compute | Per-query API calls (mitigated by persistent cache) |

### Important Limitations & Risk Disclaimers

- **Non-Stationarity:** Financial market distributions drift over time. Relationships learned on historical data may degrade or fail during regime changes.
- **Transaction Costs & Slippage:** Friction costs significantly impact active ML strategies. Real-world execution differs from simulated backtesting.
- **No Guarantee of Alpha:** Historical backtest results and high statistical test scores do not guarantee future profitability.
- **Research Only:** AlgoTrade is strictly a research and simulation platform. It does not provide financial advice and does not connect to live money trading accounts.

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
 - [x] **Phase 8.1:** Jev AI Decision Layer (TypeSafe SystemOne, 112 passing tests).
 - [x] **Phase 9:** Machine Learning feature pipeline & XGBoost predictive model (133 passing tests).
 - [x] **Phase 10:** Real-time paper-trading session daemon (architecture reserve).
 - [x] **Phase 11:** React + TypeScript interactive quantitative research platform & backtesting dashboard (139 backend tests, full frontend suite passing).

---

## Frontend Application (Phase 11)

AlgoTrade includes a high-performance, institutional-grade web application built with **React 18**, **TypeScript**, **Vite**, and **Recharts**. Designed with a professional financial-terminal aesthetic (clean typography, high information density, tabular numbers, and zero decorative AI hype), the frontend interfaces directly with the FastAPI backend.

### Frontend Architecture

```
frontend/
├── src/
│   ├── charts/
│   │   ├── CandlestickChart.tsx     # High-fidelity SVG candlestick, volume, toggleable MAs, trade markers
│   │   └── EquityDrawdownChart.tsx  # Recharts portfolio equity and underwater drawdown curves
│   ├── components/
│   │   ├── Common.tsx               # StatusBadge, MetricsGrid, TradeHistoryTable, LoadingSpinner, ErrorMessage
│   │   └── Layout.tsx               # Persistent application shell, system health checker, UTC clock, navigation
│   ├── pages/
│   │   ├── DashboardPage.tsx        # Portfolio state, active strategies, recent performance, recent experiments
│   │   ├── BacktestPage.tsx         # Interactive parameter workbench, risk limits, Jev toggles, execution
│   │   ├── StrategyLabPage.tsx      # Momentum, Mean Reversion, Pairs Trading, Moving Averages, comparison
│   │   ├── ExperimentsPage.tsx      # Filterable experiment catalog, hash verification, artifact inspector
│   │   ├── DatasetPage.tsx          # Dataset discovery and automated quantitative integrity audits
│   │   ├── MLLabPage.tsx            # Supervised XGBoost workbench (Classification vs Trading separation)
│   │   ├── JevLabPage.tsx           # Advisory LLM status, market context evaluator, decision inspector
│   │   ├── ComparisonPage.tsx       # Traditional vs XGBoost vs Jev side-by-side benchmark matrix
│   │   ├── PortfolioPage.tsx        # Cash accounting, open positions, two-leg pairs breakdown
│   │   ├── PaperTradingPage.tsx     # Simulation console with strict "NO REAL MONEY" protections
│   │   └── SettingsPage.tsx         # Configurable API base URL, simulation defaults, chart preferences
│   ├── services/
│   │   ├── api.ts                   # Centralized client with error normalization, timeouts, and URL routing
│   │   ├── datasets.ts              # Dataset catalog and validation API
│   │   ├── experiments.ts           # Experiment execution, retrieval, rerun, and multi-experiment compare
│   │   ├── backtests.ts             # Direct backtest and market bar inspection API
│   │   ├── strategies.ts            # Strategy registry and schema queries
│   │   ├── ml.ts                    # Feature metadata, model training, and walk-forward evaluations
│   │   ├── ai.ts                    # Jev status and zero-lookahead context evaluation
│   │   └── portfolio.ts             # Account summary and position accounting
│   ├── types/
│   │   └── index.ts                 # Strict TypeScript domain interfaces matching backend models without 'any'
│   ├── App.tsx                      # Hash-based application routing with zero 404s
│   ├── index.css                    # Institutional slate design system and tabular number typography
│   └── main.tsx                     # Application bootstrap
├── index.html                       # HTML shell with Inter and JetBrains Mono typography
├── vite.config.ts                   # Vite bundler, proxy configuration, and Vitest test runner
├── tsconfig.json                    # Strict TypeScript compiler options
└── package.json                     # Dependencies and build scripts
```

### Core Application Views

1. **Dashboard:** Displays portfolio equity, available cash, realized/unrealized P&L, current market exposure, maximum drawdown, active strategy registry, and recent reproducible experiment cards.
2. **Backtest Lab:** Complete research workbench. Select dataset, timeframe, strategy, customize parameters dynamically, configure risk and position sizing percentages, and toggle Jev AI advisory overlays. Executes authoritative backtests and renders the interactive candlestick chart with buy/sell/stop trade markers, performance metrics, and equity/drawdown curves.
3. **Strategy Lab:** Research quantitative strategies across Momentum, Mean Reversion, Moving Averages, and Pairs Trading. Run isolated strategy tests or execute multi-strategy comparisons via the backend comparison service without arbitrary frontend ranking scores.
4. **Experiment Repository:** Browse persisted experiments with filtering by strategy, date, or dataset. Open the detailed Experiment Inspector to examine configuration SHA-256 hashes, metrics, trade logs, and execution statistics. Rerun any experiment with 1-click deterministic verification.
5. **Dataset Manager:** View all discovered CSV datasets, row counts, and date bounds. Execute automated quantitative integrity audits displaying passed statistical checks, warnings, and errors.
6. **Machine Learning Lab:** Configure XGBoost hyperparameters, forward return horizon, and binary label thresholds. Execute model training, rolling walk-forward cross-validation, and backtesting. Strictly separates **Classification Performance** (Accuracy, Precision, Recall, F1, ROC-AUC, Brier score, Confusion Matrix) from **Trading Performance** (Return, Sharpe, Max Drawdown). Displays feature importance with formula annotations.
7. **Jev AI Lab:** Inspect Jev operational status, configured model, and decision cache statistics. Test the zero-lookahead market context evaluator and inspect structured AI decisions (`BUY`, `SELL`, `HOLD`, `NO_ACTION`) with confidence scores and latencies.
8. **Model / Provider Comparison:** Side-by-side benchmark matrix evaluating Traditional Rule-Based vs Supervised XGBoost vs Jev Advisory AI under identical initial capital and risk constraints.
9. **Portfolio & Position Manager:** Real-time simulated account balance, margin exposure, and open positions. Dedicated multi-asset pairs view displaying both legs (e.g. AAPL Long / MSFT Short) and combined net P&L.
10. **Paper Trading Console:** Simulation interface with prominent "PAPER TRADING / NO REAL MONEY" warnings.
11. **Settings:** Configurable FastAPI service base URL with live connection diagnostics and research defaults.

### Screenshot Placeholders

```
+---------------------------------------------------------------------------------------------+
|                                    [SCREENSHOT PLACEHOLDER]                                 |
|                                        AlgoTrade Dashboard                                  |
|     (Portfolio Equity, Available Cash, Recent Equity Curves, and Strategy Registry)        |
+---------------------------------------------------------------------------------------------+
|                                    [SCREENSHOT PLACEHOLDER]                                 |
|                                         Backtest Lab                                        |
|     (Interactive Candlestick Chart, Trade Execution Markers, Underwater Drawdown Curve)     |
+---------------------------------------------------------------------------------------------+
|                                    [SCREENSHOT PLACEHOLDER]                                 |
|                                     Strategy Research Lab                                   |
|      (Multi-Strategy Comparison Matrix: Momentum vs Mean Reversion vs Pairs Trading)       |
+---------------------------------------------------------------------------------------------+
|                                    [SCREENSHOT PLACEHOLDER]                                 |
|                                     Machine Learning Lab                                    |
|      (XGBoost Training, Classification Confusion Matrix vs Real-World Trading Metrics)      |
+---------------------------------------------------------------------------------------------+
|                                    [SCREENSHOT PLACEHOLDER]                                 |
|                                      Jev AI Decision Lab                                    |
|      (Zero-Lookahead Market Context Evaluator and Structured Probabilistic Decisions)       |
+---------------------------------------------------------------------------------------------+
|                                    [SCREENSHOT PLACEHOLDER]                                 |
|                                    Experiment Inspector                                     |
|      (Cryptographic Config SHA-256 Hash Verification, Full Trade Logs, and Execution Stats) |
+---------------------------------------------------------------------------------------------+
```

### Development & Build Commands

#### Backend
```powershell
# Run FastAPI server with auto-reload
python -m uvicorn backend.app.main:app --reload --port 8000

# Run complete backend test suite (139 passing tests)
pytest backend/tests -v
```

#### Frontend
```powershell
# Install frontend dependencies
cd frontend
npm install

# Start Vite local development server (port 3000)
npm run dev

# Run automated Vitest frontend test suite
npm test

# Production build and TypeScript type-check
npm run build
```