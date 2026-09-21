# AlgoTrade — ML-Enhanced Algorithmic Trading & Backtesting Platform

[![CI Pipeline](https://github.com/prithvirajsingh11/AlgoTrading/actions/workflows/ci.yml/badge.svg)](https://github.com/prithvirajsingh11/AlgoTrading/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![React 18](https://img.shields.io/badge/React-18.3+-61DAFB.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.6+-3178C6.svg)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-5.4+-646CFF.svg)](https://vitejs.dev/)
[![Tests](https://img.shields.io/badge/tests-157%20passed%20%7C%200%20failures-brightgreen.svg)](backend/tests)
[![Code Splitting](https://img.shields.io/badge/bundle-code--split%20%28171%20KB%20core%29-emerald.svg)](frontend)

**AlgoTrade** is an institutional-grade, full-stack quantitative research, event-driven backtesting, and paper-trading platform built from the ground up to showcase advanced computer science and financial engineering principles.

> **Institutional Notice:** This platform is strictly a quantitative research and simulated paper-trading laboratory. It does not connect to live money brokerage accounts or execute real monetary exchange transactions. All trading is strictly simulated.

---

## Executive Summary & Engineering Highlights

| Pillar | Implementation | Technical Distinction |
| :--- | :--- | :--- |
| **Event-Driven Backtesting** | Pure discrete-event simulation engine with chronological bar-by-bar queue. | **Zero-Lookahead Guarantee**: Signal generation strictly constrained to slice $0..t$. Intrabar high/low cross, gap execution, slippage (bps), and fixed/percentage commission modeling. |
| **Multi-Asset Statistical Arbitrage** | Cointegration pairs trading with synchronized multi-asset market snapshots. | Rolling OLS hedge ratio $\beta = \frac{\text{Cov}(P_1, P_2)}{\text{Var}(P_2)}$ calculated dynamically over sliding lookbacks; atomic simultaneous two-leg order execution. |
| **Risk & Portfolio Accounting** | Full double-entry balance sheet tracking cash, margin, and positions. | Realized vs. unrealized P&L mark-to-market reconciliation, asymmetric long/short accounting, concentration limiters, and portfolio drawdown circuit breaker. |
| **Walk-Forward Analysis** | Non-overlapping sliding windows ($Train \to Test \to Shift$). | Quarantines out-of-sample periods to prevent overfitting and data leakage; aggregates out-of-sample equity curves. |
| **Machine Learning Pipeline** | Supervised XGBoost binary classification predicting multi-horizon returns. | Purged time-series cross-validation, feature schema hash verification (SHA-256), and cryptographic artifact serialization. |
| **Advisory AI Decision Layer** | Modular Jev AI integration via TypeSafe SystemOne structured queries. | Zero-lookahead quantitative context builder, SHA-256 cache, automatic fail-safe fallback to deterministic strategy rules. |
| **Real-Time Paper Trading** | Historical replay simulation engine with discrete-speed event loop (0.5x to MAX). | SQLite event ledger, WebSocket state broadcast, sub-millisecond stepping, and server restart crash recovery (`RUNNING` $\to$ `PAUSED`). |
| **Production Engineering** | FastAPI backend with structured JSON logging, correlation IDs, and rate bounds. | Non-root Docker container (`appuser`), automated Docker healthchecks, React 18 error boundaries, and dynamic route code-splitting. |

---

## System Architecture

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
                        - Maximum Drawdown / Duration     - Real-Time WebSocket Streaming
                        - Profit Factor & Win Rate        - SQLite Event Store & State Hydration
                        - Walk-Forward Out-of-Sample      - CSV Export (Trades & Equity)
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

## Quantitative Finance Rigor

### 1. Zero-Lookahead Bias Guarantee
Many academic and hobbyist backtesters mistakenly evaluate signals using data from the current bar's close before placing orders at that same bar's open or close. AlgoTrade enforces strict point-in-time constraints:
- Signal computation for bar $t$ receives only data slice $X_{0 \dots t}$.
- Market orders generated at bar $t$ execute at bar $t+1$'s open (or bar $t$'s close with calibrated slippage penalty).
- Dynamic indicators (e.g. rolling moving averages, Bollinger bands, z-scores, ML features) utilize strictly closed historical bars.

### 2. Realistic Fill Modeling & Stop-Loss Execution
- **Intrabar Stop Crosses**: If a long stop-loss is placed at $\$95$ and the bar opens at $\$100$ with low at $\$93$, the order is filled at $\$95$.
- **Overnight Gap Down Execution**: If the market gaps down opening at $\$90$ (below the stop price of $\$95$), the order executes at the realistic worse price of $\$90$ (not the theoretical stop price).
- **Slippage & Commission Model**: Configurable basis-point execution slippage ($\Delta P = \text{Price} \times \frac{\text{bps}}{10000}$) and dual-tier commission schedule ($\text{Fixed Fee} + \text{Percentage Rate}$).

### 3. Synchronized Multi-Asset Snapshot Engine
Pairs trading and statistical arbitrage require simultaneous evaluation of multiple assets. AlgoTrade normalizes disparate time-series through an immutable `MarketSnapshot` event, guaranteeing temporal alignment and preventing asynchronous data leakage between legs.

---

## Production Hardening & Observability (Phase 13)

- **Structured JSON Logging & Sanitization**: Sensitive variables (`api_key`, `secret`, `token`, `password`) are automatically masked at log format time. Logs output standard ISO 8601 timestamps and component tags.
- **Request Correlation & Latency Tracking**: Custom ASGI middleware injects or preserves an `X-Request-ID` across every HTTP and WebSocket interaction, and returns latency in milliseconds via `X-Response-Time-MS`.
- **Server Restart Crash Recovery**: When the backend server boots, the SQLite paper-trading engine queries all active sessions. Any session previously marked as `RUNNING` is safely hydrated and transitioned to `PAUSED` with an audit notice (`"Session interrupted by server restart. Requires explicit resume."`), preventing ghost order generation or double-execution.
- **Resource Exhaustion Safeguards**: Parameter grid sweeps are bounded by `settings.max_sweep_combinations` (default 1,000) and concurrent paper sessions are bounded by `settings.max_paper_sessions` (default 20).
- **Container Security**: Backend `Dockerfile` drops root privileges to run as unprivileged `appuser`, including automated non-network `HEALTHCHECK` probes.
- **Frontend Code Splitting**: Eager page loads are refactored into `React.lazy()` dynamic imports wrapped in `<Suspense>` and a institutional-styled `<ErrorBoundary>`, shrinking the initial JavaScript payload to 171 KB.

---

## Offline Quickstart Demo

You can execute a full end-to-end demonstration of the platform 100% offline without starting servers or internet access:

```powershell
# From project root in your virtual environment:
python -m backend.app.cli demo
```

**Output:**
```text
========================================================================
    AlgoTrade -- Institutional Quant Research & Paper Engine (Demo)
========================================================================

[1/4] Discovering & Validating Datasets...
  * Dataset       : AAPL_sample
  * Total Bars    : 259
  * Quality Check : PASS (0 errors, 0 warnings)

[2/4] Executing TimeSeriesMomentum Strategy Backtest...
  * Runtime       : 39.6 ms
  * Total Return  : 4.31%
  * Sharpe Ratio  : 0.5225
  * Sortino Ratio : 0.7980
  * Max Drawdown  : 1.93%
  * Trades Exec   : 4

[3/4] Comparative Strategy Benchmark Matrix...
  --------------------------------------------------------------
  Strategy               | Return    | Sharpe   | MaxDD    | Trades
  --------------------------------------------------------------
  TimeSeriesMomentum     | 4.31%     | 0.52     | 1.93%    | 4     
  MeanReversion          | 0.79%     | -0.54    | 2.98%    | 5     
  MovingAverageCross     | 4.11%     | 0.46     | 1.71%    | 5     
  --------------------------------------------------------------

[4/4] Executing 15-Bar Paper Trading Replay Simulation...
  * Session ID    : paper_c228a1bb96
  * Replayed Bars : 15 bars
  * Final Equity  : $100,000.00 (Net: $+0.00)
  * Orders Placed : 0
  * Trades Closed : 0
  * Logged Events : 30 events

========================================================================
  AlgoTrade Demo Completed Successfully! (Exit: 0)
========================================================================
```

---

## Local Development Setup

### 1. Prerequisites
- Python 3.11+
- Node.js 20+ & npm
- Docker & Docker Compose (Optional for containerized run)

### 2. Backend Setup
```powershell
# Clone repository
git clone https://github.com/prithvirajsingh11/AlgoTrading.git
cd AlgoTrading

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows
# source .venv/bin/activate    # Linux / macOS

# Install dependencies
pip install -r backend/requirements.txt

# Run backend API server
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```
API Documentation will be live at:
- Swagger UI: `http://localhost:8000/docs`
- Redoc: `http://localhost:8000/redoc`
- Health Probe: `http://localhost:8000/health`
- Readiness Probe: `http://localhost:8000/ready`

### 3. Frontend Setup
```powershell
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser to access the institutional trading console.

### 4. Running with Docker Compose
```powershell
docker compose up --build
```

---

## Testing & Quality Assurance

AlgoTrade is continuously verified using an automated test suite across all subsystems:

```powershell
# Run backend test suite (157 unit & integration tests)
pytest backend/tests -v

# Run frontend tests (Vitest)
cd frontend
npm test -- --run

# Validate TypeScript compilation & production build
npm run build
```

**Verification Results:**
- **Backend Tests**: 157 passed, 1 skipped (optional live Jev credentials), 0 failures, 0 unexpected warnings.
- **Frontend Tests**: 6 passed, 0 failures.
- **TypeScript Build**: 0 type errors; modular code-split production bundle generated.

---

## Repository Structure

```
AlgoTrading/
├── .github/
│   └── workflows/
│       └── ci.yml                 # Automated CI pipeline (backend + frontend)
├── backend/
│   ├── app/
│   │   ├── api/                   # FastAPI route controllers
│   │   │   ├── routes_backtest.py
│   │   │   ├── routes_paper.py    # Paper trading + CSV streaming exports
│   │   │   ├── routes_ml.py       # XGBoost training & inference
│   │   │   └── ...
│   │   ├── backtesting/           # Core event-driven simulation engine
│   │   │   ├── engine.py          # Bar-by-bar queue & snapshot dispatch
│   │   │   ├── broker.py          # Stop-loss, limit, gap, slippage execution
│   │   │   ├── portfolio.py       # Mark-to-market balance sheet accounting
│   │   │   └── walk_forward.py    # Sliding window out-of-sample evaluation
│   │   ├── core/                  # Configuration, logging, and middleware
│   │   │   ├── config.py          # Pydantic v2 settings & resource limits
│   │   │   ├── logging.py         # JSON structured log formatter & redaction
│   │   │   └── middleware.py      # X-Request-ID & latency tracker
│   │   ├── ml/                    # Machine learning infrastructure
│   │   │   ├── artifacts.py       # Model serialization & integrity validation
│   │   │   ├── features.py        # Technical feature engineering
│   │   │   └── train.py           # Supervised training & evaluation
│   │   ├── paper/                 # Real-time paper trading engine
│   │   │   ├── service.py         # Session orchestration & restart recovery
│   │   │   ├── storage.py         # SQLite persistence ledger
│   │   │   └── session.py         # State machine & lifecycle management
│   │   ├── research/              # Quantitative research platform
│   │   │   ├── runner.py          # Reproducible experiment runner
│   │   │   ├── sweep.py           # Parameter grid expansion & safeguards
│   │   │   └── validator.py       # Non-throwing dataset quality validator
│   │   ├── strategies/            # Quantitative strategy implementations
│   │   │   ├── momentum.py
│   │   │   ├── mean_reversion.py
│   │   │   └── pairs_trading.py
│   │   └── main.py                # ASGI application factory & health probes
│   ├── tests/                     # 157 pytest automated tests
│   └── Dockerfile                 # Hardened multi-stage container
├── frontend/
│   ├── src/
│   │   ├── components/            # Institutional design system & ErrorBoundary
│   │   ├── pages/                 # Lazy-loaded views (Dashboard, Paper, ML Lab)
│   │   ├── services/              # Type-safe API & WebSocket clients
│   │   ├── App.tsx                # Code-splitting & route orchestration
│   │   └── main.tsx
│   └── package.json
├── data/
│   ├── raw/                       # Historical sample datasets (AAPL, MSFT, etc.)
│   └── paper/                     # Local SQLite paper-trading database
├── docker-compose.yml             # Orchestrated multi-container stack
├── pytest.ini                     # Pytest configuration & warning filters
└── README.md                      # Project documentation
```

---

## License

Distributed under the MIT License. See `LICENSE` for more information.