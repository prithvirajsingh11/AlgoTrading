# AlgoTrade — Quantitative Research, Event-Driven Backtesting & Real-Time Paper Trading Platform

[![CI Pipeline](https://github.com/prithvirajsingh11/AlgoTrading/actions/workflows/ci.yml/badge.svg)](https://github.com/prithvirajsingh11/AlgoTrading/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-v1.0.0-blue.svg)](backend/app/core/config.py)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![React 18](https://img.shields.io/badge/React-18.3+-61DAFB.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6+-3178C6.svg)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-5.4+-646CFF.svg)](https://vitejs.dev/)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](backend/tests)
[![Code Splitting](https://img.shields.io/badge/bundle-code--split%20%28171%20KB%20core%29-emerald.svg)](frontend)

> **SIMULATION / RESEARCH PLATFORM — NOT REAL-MONEY TRADING SOFTWARE**
> AlgoTrade is strictly a quantitative research, deterministic backtesting, and paper-trading simulation platform built with production-oriented engineering practices. It contains **zero live-broker order execution endpoints** and executes **zero real-money financial transactions**. All orders route strictly to `SimulatedBroker`.

---

## 1. One-Sentence Description
A portfolio-ready, full-stack quantitative research, event-driven backtesting, and real-time paper-trading platform engineered in Python (FastAPI) and TypeScript (React) to demonstrate rigorous financial engineering, deterministic reproducibility, and production-oriented software design.

---

## 2. Overview
AlgoTrade bridges the divide between theoretical quantitative research and production-oriented trading software. Designed from first principles, it provides a comprehensive end-to-end environment for strategy formulation, statistical arbitrage, machine learning cross-validation, LLM-assisted advisory reasoning, discrete-event backtesting, and real-time paper trading with WebSocket streaming.

The platform eliminates common backtesting pitfalls—such as lookahead bias, survivorship bias, unrealistic instant fills, and unmodeled transaction costs—by utilizing discrete-event processing, strict point-in-time data scoping, intrabar high/low crossing logic, gap execution modeling, basis-point slippage, and quadratic market impact simulation.

---

## 3. Why I Built This
Most open-source algorithmic trading frameworks suffer from several systemic flaws:
1. **Vectorized Lookahead Leakage**: Many backtesters evaluate signals across entire pandas dataframes at once, accidentally leaking future prices into historical decision timestamps.
2. **Naive Execution Assumptions**: Theoretical backtests often assume orders fill instantly at the bar close price without slippage, market impact, or commission friction.
3. **Fragile State Management**: Paper-trading systems often lack crash-recovery semantics, losing state when a connection drops or a server restarts.
4. **Opaque AI Integration**: Modern AI trading tools often hallucinate decisions without quantitative grounding or verifiable cryptographic provenance.

AlgoTrade was built to solve these challenges with rigorous software engineering: a pure discrete-event state machine, point-in-time scoping, verifiable SHA-256 reproducibility hashes, double-entry portfolio accounting, fail-safe advisory AI boundaries, and asynchronous WebSocket synchronization with circuit breakers.

---

## 4. Architecture

![AlgoTrade System Architecture](docs/architecture.svg)

```
                                  [ Historical / Live OHLCV Ingestion ]
                                                    │
                                                    ▼
                                    [ Non-Throwing Dataset Validator ]
                             (Checks chronological order, duplicates, NaNs, spikes)
                                                    │
                                                    ▼
      ┌───────────────────────────────── [ Core Trading Pipeline ] ─────────────────────────────────┐
      │                                                                                             │
      │   For each bar t (Strictly Chronological):                                                  │
      │   ┌─────────────────────────────────────────────────────────────────────────────────────┐   │
      │   │ 1. Simulated Broker : Check pending stops/limits; fill against bar High/Low/Open    │   │
      │   │ 2. Portfolio Engine : Mark-to-market positions at current Bar Close                 │   │
      │   │ 3. Quant Strategy   : MovingAverage, Momentum, MeanReversion, or Pairs Arbitrage     │   │
      │   │                       (Strictly evaluates history slice [0..t] — Zero Lookahead)    │   │
      │   │ 4. ML / AI Advisor  : (Optional) XGBoost inference or Jev AI market evaluation      │   │
      │   │ 5. Position Sizer   : Equity % sizing or Risk-Based volatility sizing                │   │
      │   │ 6. Risk Manager     : Authoritative gate checking cash, concentration & drawdown    │   │
      │   │ 7. Execution Engine : Execute fill with slippage model + tiered commission schedule │   │
      │   │ 8. Ledger Update    : Update cash, open positions, realized/unrealized P&L          │   │
      │   └─────────────────────────────────────────────────────────────────────────────────────┘   │
      │                                                                                             │
      └───────────────────────────────┬─────────────────────────────┬───────────────────────────────┘
                                      │                             │
                                      ▼                             ▼
                        [ Backtest Analytics Engine ]     [ Paper Trading Engine ]
                        - Sharpe / Sortino Ratio          - Historical Bar Replay (0.5x-MAX)
                        - Maximum Drawdown / Duration     - Synthetic & Live WebSocket Streaming
                        - Profit Factor & Win Rate        - SQLite Event Store & State Hydration
                        - Walk-Forward Out-of-Sample      - CSV / JSON / MD Export Engine
                                      │                             │
                                      └──────────────┬──────────────┘
                                                     │
                                                     ▼
                                       [ FastAPI REST & WebSocket API ]
                                       - Structured JSON Logging & X-Request-ID
                                       - Liveness (/health) & Readiness (/ready)
                                       - Sanitized Global 500 Error Handler
                                                     │
                                                     ▼
                                     [ React 18 / TypeScript Console ]
                                     - Lazy-loaded modular chunks (171 KB core)
                                     - Runtime UI ErrorBoundary protection
                                     - Recharts institutional performance curves
```

---

## 5. Core Features
- **Discrete-Event Simulation Engine**: Bar-by-bar queue with strictly chronological execution.
- **Strict Zero-Lookahead Scoping**: Mathematical guarantee that bar $t$ evaluates only data from slice $[0 \dots t]$.
- **Execution Modeling**: Realistic intrabar stop crossing, overnight gap handling, fixed basis-point slippage, quadratic market impact, and configurable commission structures.
- **Statistical Arbitrage**: Multi-asset pairs trading with rolling dynamic OLS hedge ratio $\beta = \frac{\text{Cov}(P_1, P_2)}{\text{Var}(P_2)}$ and atomic dual-leg execution.
- **Supervised ML Pipeline**: XGBoost classification predicting directional returns with purged time-series cross-validation and SHA-256 schema verification.
- **Jev AI Advisory Layer**: Quantitative context formulation with zero lookahead, deterministic caching, and graceful fallback to rule-based execution.
- **Interactive Paper Trading**: Live tick-to-bar aggregation, bounded streaming feature updates, and crash recovery with SQLite WAL persistence.
- **Safety Circuit Breakers**: Stale data watchdog (auto-pauses signals after 30s silence) and portfolio drawdown auto-liquidation.
- **Comprehensive Reporting**: Multi-format exports (JSON, CSV, Markdown) with SHA-256 cryptographic provenance.

---

## 6. Trading Strategies
AlgoTrade ships with four production-tested quantitative strategies:

1. **Moving Average Crossover (`MovingAverageCrossover`)**:
   - Classical trend-following identifying regime shifts between fast ($N_{fast}$) and slow ($N_{slow}$) exponential moving averages.
2. **Time-Series Momentum (`TimeSeriesMomentum`)**:
   - Evaluates multi-period normalized rate-of-change with rolling volatility scaling and dynamic threshold entry filters.
3. **Mean Reversion / Bollinger Bands (`MeanReversion`)**:
   - Identifies statistical extremes in asset prices using rolling standard deviation bands ($K \times \sigma$) with center-line reversion targets.
4. **Statistical Arbitrage / Pairs Trading (`PairsTrading`)**:
   - Synchronizes multi-asset snapshots across cointegrated pairs (e.g. AAPL/MSFT), computes the dynamic rolling OLS spread z-score:
     $$Z_t = \frac{(P_{1,t} - \beta P_{2,t}) - \mu_{\text{spread}}}{\sigma_{\text{spread}}}$$
   - Executes simultaneous atomic long/short orders when $|Z_t| > Z_{\text{entry}}$ and unwinds at $|Z_t| < Z_{\text{exit}}$.

---

## 7. Risk Management
Risk controls are enforced authoritatively by `RiskManager` before any order is submitted to `SimulatedBroker`:
- **Capital Allocation Bounds**: Prevents any single position from exceeding a maximum fraction of total portfolio equity (default: 20%).
- **Gross Leverage Limits**: Restricts aggregate long and short exposure to predefined regulatory thresholds.
- **Drawdown Circuit Breaker**: Continuously evaluates high-water mark equity; halts new order generation if peak-to-trough drawdown exceeds configurable limits (default: 15%).
- **Order Size Validation**: Enforces minimum/maximum lot sizes and validates sufficient available cash and margin before dispatch.

---

## 8. Backtesting
The backtest engine operates on an immutable chronological event loop:
- **Order Execution Lifecycle**: Market orders execute at next-bar Open; Stop-Loss and Take-Profit orders monitor High/Low ranges for realistic intrabar crossing.
- **Overnight Gap Down Logic**: If an asset opens below a protective stop price, the fill occurs at the Open price rather than the theoretical stop price.
- **Quantitative Metrics**:
  - Annualized Return (CAGR)
  - Annualized Volatility
  - Sharpe Ratio ($R_f = 0.0$)
  - Sortino Ratio (downside semivariance)
  - Maximum Drawdown (%) and Peak-to-Trough Duration
  - Win Rate (%) and Profit Factor ($\frac{\sum \text{Gains}}{\sum |\text{Losses}|}$)
  - Calmar Ratio and Expectancy per Trade

---

## 9. Research & Reproducibility
- **Walk-Forward Optimization**: Evaluates strategy parameters across rolling train/test windows ($Train \to Test \to Shift$) to quarantine out-of-sample data and diagnose parameter decay.
- **Parameter Sweeps**: Grid search across multi-dimensional hyperparameter spaces with concurrent evaluation.
- **Cryptographic Provenance**: Every experiment run generates a deterministic SHA-256 hash derived from the exact strategy parameters, dataset metadata, and execution assumptions.
- **Non-Throwing Dataset Validation**: Scans datasets for chronological inversions, timestamp duplicates, non-positive prices, NaNs, and volume anomalies without crashing.

---

## 10. Machine Learning
AlgoTrade integrates an end-to-end supervised machine learning pipeline:
- **Feature Engineering**: Incremental technical features including multi-period returns, rolling volatility, RSI, MACD, and Bollinger band widths.
- **Purged Cross-Validation**: Prevents information leakage between adjacent bars by introducing purge windows between training and testing folds.
- **Model Training**: XGBoost binary classifier predicting whether forward $k$-period return exceeds transaction cost thresholds.
- **Artifact Verification**: Serialized models include a SHA-256 feature schema hash, preventing inference with mismatched feature sets.
- **Classification vs. Trading Performance**: Machine learning metrics (Accuracy, ROC-AUC, F1 score, Log Loss) evaluate statistical return predictability and are strictly distinguished from trading performance metrics (Sharpe ratio, CAGR, Max Drawdown). High classification accuracy does not guarantee trading profitability due to execution slippage, spread, and transaction costs.

---

## 11. Jev AI Advisory/Decision Layer
AlgoTrade features a structured AI advisory layer powered by Jev / SystemOne:
- **Advisory Role**: Operates strictly as an advisory overlay on top of deterministic quantitative strategies, never as a guaranteed predictor, profitable trading oracle, autonomous live trader, or guaranteed decision maker.
- **Quantitative Context Packaging**: Packages point-in-time market data, technical indicators, and current portfolio positions into a structured JSON payload without future leakage.
- **Deterministic Caching**: Caches responses against the SHA-256 hash of the input context to prevent redundant inference calls.
- **Operating Modes**:
  - `MOCK / TEST PROVIDER`: Used for deterministic offline tests and demonstrations without external API dependencies.
  - `CACHED_JEV`: Replays cached decisions matching input context hash.
  - `LIVE_JEV`: Live advisory queries via secure external API.
- **Graceful Fallback**: If the advisory service is unavailable, unconfigured, or returns an error, the engine seamlessly falls back to pure deterministic strategy logic.

---

## 12. Real-Time Market Data
AlgoTrade provides a vendor-agnostic real-time market data streaming architecture:
- **Provider Abstraction (`RealTimeMarketDataProvider`)**: Standardized interface for live and streaming feeds.
- **Alpaca WebSocket v2 Adapter**: Concrete adapter supporting live quote and trade streaming with zero credential leakage in logs or responses.
- **Tick-to-Bar Aggregator (`TickToBarAggregator`)**: Aggregates raw trades into time-bucketed OHLCV bars in memory.
- **Multi-Asset Synchronizer (`MultiAssetSynchronizer`)**: Aligns multi-symbol streaming feeds, discarding or holding unsynchronized bars until temporal alignment is verified.
- **Stale Data Watchdog**: Automatically transitions from `SIGNALS_ENABLED` to `SIGNALS_PAUSED` if feed silence exceeds 30 seconds, preserving existing trailing stops while preventing stale order submission.

---

## 13. Paper Trading
The paper trading subsystem provides simulated execution:
- **Deterministic Historical Replay**: Steps through historical bars at controlled replay speeds (0.5x to MAX).
- **Synthetic Live Streaming**: Generates real-time geometric Brownian motion ticks for offline demonstration and testing.
- **State Hydration**: Persists positions, trades, orders, and equity curves to SQLite using Write-Ahead Logging (WAL).
- **Crash Recovery**: Automatically reconstructs open positions and execution ledgers upon session restart.
- **Export Capabilities**: Exports trade blotters and equity curves to CSV and JSON formats.

---

## 14. Three Operating Modes
AlgoTrade strictly separates its operational workflows into three distinct modes:

| Mode | Market Data Source | Execution Destination | Typical Use Case |
| :--- | :--- | :--- | :--- |
| **`HISTORICAL_REPLAY`** | Historical OHLCV dataset | `SimulatedBroker` | Backtesting, parameter sweeps, walk-forward analysis |
| **`SYNTHETIC_STREAM`** | In-memory GBM tick generator (`[SYNTHETIC TEST FEED]`) | `SimulatedBroker` | Offline paper trading, UI demonstration, integration testing |
| **`REAL_TIME`** | Live external WebSocket feed (e.g. Alpaca v2) | `SimulatedBroker` | Real-time paper trading, forward testing with live market feeds |

> **Safety Notice:** In `REAL_TIME` mode, if API credentials are not provided, the provider transitions cleanly to `NOT_CONFIGURED` without falling back to fake data. Real-time mode is for market data ingestion only; all order execution remains simulated.

---

## 15. Performance Benchmarks
> **DISCLAIMER: LOCAL SYNTHETIC BENCHMARKS**
> All metrics recorded below represent a **local synthetic software-performance benchmark**, **measured on deterministic GBM datasets in the development environment**.
>
> Benchmark results do **NOT** represent exchange latency, brokerage execution latency, production infrastructure performance, trading profitability, or investment performance. Zero claims of trading profitability are made.

The benchmark engine measures 7 subsystems on local hardware:

| # | Subsystem | Measured Metric | Measured Performance | Performance Target | Status |
| :- | :--- | :--- | :--- | :--- | :--- |
| **1** | **Dataset ingestion** | Ingestion Throughput | **123,047 bars/sec** | $\ge 5,000$ bars/sec | **PASS (+2,360%)** |
| **2** | **Streaming feature engine** | Incremental Bar Latency | **18.7 µs / bar** (53,475 bars/s) | $\le 5,000$ µs / bar | **PASS (+26,600%)** |
| **3** | **Strategy signal generation** | Signal Compute Latency | **12.4 µs / bar** (80,645 bars/s) | $\le 1,000$ µs / bar | **PASS (+7,900%)** |
| **4** | **Event-driven backtesting** | Event Simulation Throughput | **2,418 bars/sec** | $\ge 200$ bars/sec | **PASS (+1,100%)** |
| **5** | **Paper-step replay** | Step Execution Latency | **1,120 µs / step** | $\le 5,000$ µs / step | **PASS (+346%)** |
| **6** | **WebSocket serialization** | Event JSON Serialization | **18,450 msgs/sec** | $\ge 1,000$ msgs/sec | **PASS (+1,745%)** |
| **7** | **Peak memory allocation** | Peak Memory Delta | **0.84 MB** | $\le 50.0$ MB | **PASS (+5,850%)** |

---

## 16. Security & Safety
- **Zero Live Broker Connections**: Enforced by static AST invariant tests (`backend/tests/test_no_brokerage_imports.py`). Any import of live order placement libraries triggers test failure.
- **Zero Credential Leakage**: API secrets are stored strictly in environment variables; logs and endpoints mask or redact sensitive credentials.
- **Non-Root Docker Execution**: Docker containers run under an unprivileged `appuser` (UID 10001).
- **Sanitized Error Handling**: Global 500 exception handlers catch unhandled errors and return generic error IDs with correlation tracking, preventing stack trace disclosure.
- **CORS & Rate Limiting**: Strict CORS origin whitelisting and API rate limiting on public endpoints.

---

## 17. Technology Stack
- **Backend**: Python 3.11+, FastAPI, Pydantic v2, NumPy, Pandas, SciPy, XGBoost, Uvicorn, SQLite (WAL mode).
- **Frontend**: React 18, TypeScript 5.6+, Vite 5.4+, TailwindCSS, Lucide Icons, Recharts.
- **Testing & Verification**: Pytest, Pytest-Asyncio, Vitest, Testing Library, ESLint, Static AST Scanners.
- **DevOps**: Docker (multi-stage non-root), GitHub Actions CI/CD.

---

## 18. Installation

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- Git

### Setup
```bash
# Clone the repository
git clone https://github.com/prithvirajsingh11/AlgoTrading.git
cd AlgoTrading

# Set up Python virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install backend dependencies
pip install -r backend/requirements.txt

# Install frontend dependencies
cd frontend
npm install
cd ..
```

---

## 19. Running Locally

### Start Backend API Server
```bash
# From project root
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
The interactive Swagger API documentation is available at `http://localhost:8000/docs`.

### Start Frontend Development Server
```bash
# In another terminal
cd frontend
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 20. Running the Demo
AlgoTrade provides a 100% offline, deterministic end-to-end CLI demonstration covering all platform subsystems:

```bash
python -m backend.app.cli demo
```

The demo executes a 10-stage offline demo workflow:
1. **Dataset discovery and validation**: Loads and validates the 5,000-bar AAPL dataset.
2. **Deterministic backtest**: Runs `TimeSeriesMomentum` strategy with full metrics calculation.
3. **Strategy comparison**: Compares 4 strategies side-by-side with risk-adjusted rankings.
4. **XGBoost evaluation**: Evaluates out-of-sample classification performance and feature importance.
5. **Jev status/mock advisory demonstration**: Demonstrates advisory context packaging and mock decision inference (`[MOCK / TEST PROVIDER]`).
6. **Synthetic paper stream**: Initiates an in-memory streaming session tagged `[SYNTHETIC TEST FEED]`.
7. **Risk rejection demonstration**: Submits an oversized order that triggers concentration risk rejection.
8. **Simulated order execution**: Fills a compliant order, updates the portfolio, and calculates P&L.
9. **Failure recovery**: Simulates feed loss, verifies safety circuit breaker, and recovers.
10. **Export**: Generates `demo_paper_export.json`, `demo_paper_trades.csv`, and `demo_experiment_report.md`.

---

## 21. Running Tests

```bash
# Run all backend unit and integration tests (229 passed, 1 skipped)
pytest

# Run tests with coverage
pytest --cov=backend/app --cov-report=term-missing

# Run frontend tests
cd frontend
npm test -- --run
cd ..

# Run production frontend build
cd frontend
npm run build
cd ..
```

---

## 22. Docker

### Build and Run with Docker Compose
```bash
docker-compose up --build
```
The application will be accessible at:
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Healthcheck: `http://localhost:8000/health`

---

## 23. CI/CD
AlgoTrade utilizes GitHub Actions for continuous integration (`.github/workflows/ci.yml`). Every pull request and push to `main` executes:
1. Python linting and code formatting verification.
2. Static AST invariant scanning (verifying zero live-broker order imports).
3. Backend test suite execution across Python 3.11.
4. Frontend TypeScript type checking, linting, and Vitest suite execution.
5. Production bundle build and asset size validation.

---

## 24. Project Structure
```
AlgoTrading/
├── backend/
│   ├── app/
│   │   ├── api/             # REST routes & WebSocket endpoints
│   │   ├── backtesting/     # Engine, broker, portfolio, risk manager, ledger
│   │   ├── core/            # Configuration, logging, security, correlation
│   │   ├── ml/              # Feature engineering, XGBoost training, cross-validation
│   │   ├── paper/           # Paper trading service, feed aggregator, synchronizer
│   │   ├── research/        # Datasets, walk-forward analysis, parameter sweeps
│   │   ├── strategies/      # Moving average, momentum, mean reversion, pairs
│   │   ├── cli.py           # CLI entrypoint (demo, benchmark, backtest)
│   │   └── main.py          # FastAPI application factory & lifecycle
│   └── tests/               # 229+ unit, integration, and security tests
├── frontend/
│   ├── src/
│   │   ├── components/      # Modular UI components & layout
│   │   ├── pages/           # Dashboard, Backtest, ML, Paper Trading, Settings
│   │   ├── services/        # API client & WebSocket client
│   │   └── types/           # TypeScript interfaces matching backend models
│   └── package.json
├── configs/                 # Deterministic demo and backtest configurations
├── data/demo/               # Seeded offline datasets (5,000 bars)
├── docs/                    # Architectural diagrams, benchmarks, specifications
│   ├── assets/              # SVG UI mockups for all major interfaces
│   ├── architecture.svg     # Full platform vector architecture diagram
│   ├── technical-design.md  # Detailed technical design specification
│   ├── project-summary.md   # Technical project summary
│   ├── benchmarks.md        # Detailed performance benchmark report
│   ├── limitations.md       # Platform limitations & assumptions
│   └── release-checklist.md # Production release readiness audit
├── reports/                 # Exported experiment reports (JSON, CSV, Markdown)
├── docker-compose.yml       # Production multi-container composition
└── README.md
```

---

## 25. Limitations
AlgoTrade is designed as a simulation and research platform. Detailed discussion of assumptions and constraints is documented in [`docs/limitations.md`](docs/limitations.md):
- **Slippage Calibration**: Uses a constant basis-point and quadratic impact model; does not reconstruct the full limit order book depth (L2/L3).
- **Borrow Rates**: Short selling assumes infinite borrow availability without hard-to-borrow fees or borrow recalls.
- **Latency Invariants**: Backtest assumes deterministic chronological ordering without network jitter or packet loss.

---

## 26. Future Work
- **Limit Order Book (LOB) Simulation**: Level 2 order book matching engine with price-time priority queues.
- **Factor Risk Models**: Multi-factor risk decomposition (Barra-style fundamental and statistical risk factors).
- **Reinforcement Learning**: Deep Q-Learning (DQN) and PPO agents for automated execution slicing.
- **Options & Derivatives**: Black-Scholes pricing, implied volatility surface modeling, and delta-neutral hedging.

---

## 27. Computer Science Concepts Demonstrated
AlgoTrade was architected to demonstrate core computer science and software engineering principles:

1. **Discrete-Event Simulation (State Machine)**:
   - State advances strictly upon discrete timestamp events rather than continuous clock ticks, guaranteeing deterministic execution regardless of host CPU speed.
2. **Sliding Window Algorithms ($O(1)$ Online Features)**:
   - Moving averages, standard deviations, and RSI indicators compute incrementally using rolling buffers without re-scanning full historical arrays.
3. **Purged Time-Series Splits (Data Leakage Prevention)**:
   - Eliminates lookahead bias and autocorrelation leakage in cross-validation through temporal purging and embargo windows.
4. **Cryptographic Provenance (SHA-256 Hashing)**:
   - Experiment configurations, datasets, and feature schemas are cryptographically hashed to guarantee 100% reproducible results.
5. **Static AST Analysis (Security Verification)**:
   - Python `ast` module parses the codebase at test time to verify zero forbidden live-money broker imports exist.
6. **Dynamic Route Code-Splitting (Frontend Optimization)**:
   - Vite and React `lazy` split analytical pages into isolated chunks, reducing initial bundle weight to 171 KB core.
7. **Bounded Ring-Buffer Memory Management**:
   - Streaming ticks and bars are stored in bounded ring buffers (`collections.deque(maxlen=N)`), preventing memory leaks during long-running sessions.
8. **Asynchronous Producer-Consumer Pipeline**:
   - WebSocket streaming decouples market ingestion from order dispatch using asyncio queues and backpressure safeguards.

---

## 28. Screenshot & Diagram Gallery

| View | Preview | Description |
| :--- | :--- | :--- |
| **System Architecture** | [Architecture Diagram](docs/architecture.svg) | Full-stack dataflow, core trading pipeline, paper trading, and analytics |
| **Main Dashboard** | [Dashboard SVG](docs/assets/dashboard.svg) | Portfolio overview, active sessions, real-time telemetry, and risk metrics |
| **Backtest Lab** | [Backtest Lab SVG](docs/assets/backtest_lab.svg) | Configuration panel, equity curve, drawdown chart, and execution blotter |
| **Strategy Comparison** | [Strategy Matrix SVG](docs/assets/strategy_comparison.svg) | Multi-strategy comparative matrix, Sharpe rankings, and return metrics |
| **Machine Learning Lab** | [ML Lab SVG](docs/assets/ml_lab.svg) | Feature importance bar chart, ROC curve, and confusion matrix |
| **Jev AI Decision Layer** | [Jev Advisory SVG](docs/assets/jev_lab.svg) | Structured market context packaging, LLM reasoning, and strategy overlays |
| **Paper Trading Console** | [Paper Trading SVG](docs/assets/paper_trading.svg) | Live order blotter, position monitor, and historical/synthetic streaming |
| **Real-Time Data Provider** | [Real-Time Provider SVG](docs/assets/realtime_provider.svg) | Live WebSocket adapter, bar aggregator, multi-asset synchronizer, telemetry |
| **Experiment Details** | [Experiment Details SVG](docs/assets/experiment_details.svg) | SHA-256 config hash, execution assumptions, equity curve, and blotter |

---

## License
MIT License. See [LICENSE](LICENSE) for details.