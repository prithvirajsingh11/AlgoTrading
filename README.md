# AlgoTrade — ML-Enhanced Algorithmic Trading & Backtesting Platform

A computer science portfolio project implementing a quantitative trading research, event-driven backtesting, and paper-trading platform.

> **Disclaimer:** This platform is strictly for research and simulated paper trading. It does not connect to real-money brokerage accounts or execute live monetary transactions.

---

## Key Features (Phases 1–7)

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
  - 51 unit and integration tests covering all critical components.

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
│   │   │   └── routes_paper.py        # Paper trading session stubs
│   │   ├── core/
│   │   │   ├── config.py              # Pydantic configuration & env loading
│   │   │   └── database.py            # Database session & engine setup
│   │   ├── data/
│   │   │   ├── loader.py              # CSV loader & OHLCV bar dataclass
│   │   │   ├── cleaner.py             # Data integrity & chronology validation
│   │   │   └── features.py            # Technical indicators (SMA, EMA, Volatility)
│   │   ├── strategies/
│   │   │   ├── base.py                # BaseStrategy abstract class
│   │   │   ├── momentum.py            # MovingAverageCrossStrategy
│   │   │   ├── mean_reversion.py      # Stub for subsequent phase
│   │   │   ├── pairs_trading.py       # Stub for subsequent phase
│   │   │   └── ml_strategy.py         # Stub for subsequent phase
│   │   ├── backtesting/
│   │   │   ├── engine.py              # Chronological event-driven engine
│   │   │   ├── broker.py              # Simulated broker (slippage, fees, limits)
│   │   │   ├── orders.py              # Order, Signal, Trade data models
│   │   │   └── portfolio.py           # Cash, positions, and equity accounting
│   │   ├── risk/
│   │   │   ├── position_sizing.py     # Sizing algorithms (Fixed, % Equity)
│   │   │   ├── risk_manager.py        # Risk checks & circuit breaker
│   │   │   └── metrics.py             # Quantitative performance calculations
│   │   ├── ml/
│   │   │   ├── features.py            # ML feature extraction stubs
│   │   │   ├── train.py               # Model training stubs
│   │   │   ├── evaluate.py            # Model evaluation stubs
│   │   │   └── model.py               # ML model wrapper stub
│   │   └── main.py                    # FastAPI application entry point
│   ├── tests/                         # Comprehensive pytest test suite
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

All 35 tests verify:
- Order lifecycle and validation
- Simulated broker execution, slippage, and commissions
- Portfolio cash and position accounting
- Pre-trade risk controls and circuit breakers
- Moving average crossover signal generation
- Quantitative performance metric formulas
- Event-driven engine chronology and no-lookahead guarantees
- FastAPI REST endpoints

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

## Roadmap

 - [x] **Phase 1:** Project foundation and modular architecture.
 - [x] **Phase 2:** Historical market data loader, cleaning, and validation.
 - [x] **Phase 3:** Event-driven backtesting engine, simulated broker, and portfolio accounting.
 - [x] **Phase 4:** Moving Average Crossover momentum strategy.
 - [x] **Phase 5:** Quantitative performance metrics (Sharpe, Sortino, Max Drawdown).
 - [x] **Phase 6:** Automated test suite (35 passing tests).
 - [x] **Phase 7:** Strategy expansion (Momentum, Mean Reversion, Pairs Trading), Risk Sizing, Stop-Loss, Walk-Forward backtester, and Strategy Comparator (51 passing tests).
 - [x] **Phase 7.1:** True Multi-Asset Pairs Trading & Realistic Stop-Loss Execution (70 passing tests).
 - [ ] **Phase 8:** Machine Learning feature pipeline & XGBoost predictive model.
 - [ ] **Phase 9:** Real-time paper-trading session daemon.
 - [ ] **Phase 10:** React + TypeScript interactive analytics dashboard.