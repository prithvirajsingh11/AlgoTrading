# AlgoTrade — Technical Design Specification (v1.0.0)

> **SIMULATION / RESEARCH PLATFORM — NOT REAL-MONEY TRADING SOFTWARE**
> AlgoTrade is a portfolio-ready algorithmic-trading research and paper-trading platform engineered for quantitative experimentation, discrete-event backtesting, and real-time market data streaming. All order execution is handled strictly by `SimulatedBroker`. The platform contains zero live brokerage order execution endpoints and executes zero real-money transactions.

---

## 1. System Architecture Overview

AlgoTrade is architected as an asynchronous, event-driven trading simulation platform that strictly separates market ingestion, quantitative decision logic, risk authorization, simulated order execution, and portfolio accounting.

```
                              [ Market Data Ingestion ]
                    (Historical CSV / Synthetic GBM / WebSocket)
                                         │
                                         ▼
                             [ Dataset & Feed Validator ]
                      (Chronological, Non-Negative, NaN-Checked)
                                         │
                                         ▼
                     ┌────────────────────────────────────────┐
                     │          Backtest / Paper Loop         │
                     │  1. Simulated Broker: check pending    │
                     │  2. Portfolio Engine: mark-to-market   │
                     │  3. Strategy: generate signal (0..t)   │
                     │  4. ML / Jev Advisor: advisory score   │
                     │  5. Position Sizer: risk-based sizing  │
                     │  6. Risk Manager: gate check           │
                     │  7. Execution Engine: fill with cost   │
                     │  8. Ledger Update: cash & positions    │
                     └───────────────────┬────────────────────┘
                                         │
                        ┌────────────────┴────────────────┐
                        ▼                                 ▼
             [ Research Analytics ]            [ Paper Trading Engine ]
             - Sharpe / Sortino Ratios         - Real-time tick aggregation
             - Drawdown duration               - Multi-asset synchronizer
             - Walk-forward splits             - SQLite WAL persistence
             - Cryptographic provenance        - WebSocket event stream
```

---

## 2. Core Subsystems

### 2.1 Discrete-Event Simulation Engine
- **Bar-by-Bar Queue**: Backtests process sequential `MarketBar` events strictly in chronological order.
- **Zero-Lookahead Guarantee**: At timestamp $t$, the strategy and feature pipelines only receive historical data up to and including slice $[0 \dots t]$. Forward prices are strictly inaccessible.
- **Execution Lifecycle**: Market orders generated at bar $t$ execute against bar $t+1$'s Open price (or bar $t$'s Close with explicit latency penalty).

### 2.2 Execution & Microstructure Modeling
- **Intrabar Stop Crossing**: Stop-loss orders monitor high/low ranges of subsequent bars. If a stop level is crossed intrabar, the fill price is calculated realistically:
  - If bar opens beyond stop price (overnight gap down), the fill executes at the Open price.
  - If stop price lies within $[Low, High]$, the fill executes at the stop price.
- **Slippage Modeling**: Configurable basis-point slippage ($\Delta P = P \times \frac{\text{bps}}{10000}$) and quadratic market impact modeling:
  $$\text{Impact} = \alpha \cdot \text{Price} \cdot \left(\frac{\text{OrderQty}}{\text{BarVolume}}\right)^2$$
- **Commission Modeling**: Tiered commission schedules supporting fixed per-trade fees and percentage-of-notional fees.

### 2.3 Authoritative Risk Management (`RiskManager`)
Before any signal reaches the broker, it must pass authoritative pre-trade checks:
1. **Cash & Margin Validation**: Verifies that available cash covers order notional, margin requirements, and estimated transaction fees.
2. **Concentration Limit**: Restricts any single asset position from exceeding a maximum fraction of total portfolio equity (default: 20%).
3. **Gross Leverage Limit**: Prevents aggregate gross exposure from exceeding predefined risk thresholds.
4. **Portfolio Drawdown Circuit Breaker**: Evaluates peak-to-trough equity drawdown from the high-water mark; halts new risk-increasing orders if drawdown breaches limits (default: 15-25%).

### 2.4 Accounting & Double-Entry Ledger (`Portfolio`)
- **Ledger Records**: Maintains explicit double-entry records for all cash inflows, outflows, realized trade P&L, commissions, and financing costs.
- **Mark-to-Market Revaluation**: Revalues open positions on every market close event, calculating unrealized P&L and total equity dynamically.
- **Asymmetric Long/Short Accounting**: Accurately tracks short borrow liabilities and collateral requirements.

### 2.5 Quantitative Strategies
The platform includes four standard quantitative strategies:
1. **`MovingAverageCrossover`**: Dual exponential moving average trend-following strategy.
2. **`TimeSeriesMomentum`**: Normalized rate-of-change momentum strategy with rolling volatility targeting.
3. **`MeanReversion`**: Bollinger band mean-reversion strategy targeting statistical extremes.
4. **`PairsTrading`**: Statistical arbitrage strategy for cointegrated pairs computing rolling OLS spread z-scores:
   $$Z_t = \frac{(P_{1,t} - \beta P_{2,t}) - \mu_{\text{spread}}}{\sigma_{\text{spread}}}$$
   Executes simultaneous atomic dual-leg orders.

### 2.6 Supervised Machine Learning Pipeline (`XGBoost`)
- **Classification Performance vs Trading Performance**: Clearly distinguishes classification metrics (Accuracy, ROC-AUC, F1, Log Loss) from backtested economic performance (Sharpe, Return, Drawdown). High classification accuracy does not imply trading profitability.
- **Purged Cross-Validation**: Uses temporal purging and embargo windows to prevent autocorrelation leakage between training and testing sets.
- **Cryptographic Model Verification**: Generates a deterministic SHA-256 schema hash of input feature names and types, verifying feature alignment prior to inference.

### 2.7 Jev AI Advisory Layer
- **Advisory Role**: Operates strictly as an advisory overlay on top of quantitative strategies, never as an autonomous live trader or guaranteed decision maker.
- **Context Packaging**: Packages point-in-time technical features, portfolio metrics, and market regime into a structured, zero-lookahead JSON payload.
- **Deterministic Caching**: Stores responses indexed by the SHA-256 hash of the input context.
- **Modes**:
  - `MOCK / TEST PROVIDER`: Offline mock provider for testing and deterministic demonstration.
  - `CACHED_JEV`: Replays cached decisions matching input context hash.
  - `LIVE_JEV`: Live advisory queries via secure external API.
- **Graceful Degradation**: Automatically falls back to deterministic strategy rules if the advisory service is unavailable or unconfigured.

### 2.8 Real-Time Paper Trading & Streaming Infrastructure
- **Three Operating Modes**:
  1. `HISTORICAL_REPLAY`: Replays historical OHLCV data at controlled speeds.
  2. `SYNTHETIC_STREAM`: Generates in-memory Geometric Brownian Motion ticks tagged `[SYNTHETIC TEST FEED]`.
  3. `REAL_TIME`: Connects to live external WebSocket market data feeds (e.g. Alpaca v2) for market data ingestion only.
- **Tick-to-Bar Aggregator (`TickToBarAggregator`)**: Bounded in-memory aggregation of raw trade ticks into interval OHLCV bars.
- **Multi-Asset Synchronizer (`MultiAssetSynchronizer`)**: Aligns multi-symbol streaming feeds, enforcing maximum allowable desynchronization thresholds.
- **Stale Data Watchdog**: Transitions trading state from `SIGNALS_ENABLED` to `SIGNALS_PAUSED` if feed silence exceeds 30 seconds, preserving active trailing stops.
- **Crash Recovery & Persistence**: SQLite Write-Ahead Logging (WAL) persists all orders, trades, and portfolio snapshots, enabling state hydration upon restart.

---

## 3. Security & Safety Invariants

1. **Paper-Only Execution Invariant**:
   - `Signal` $\to$ `RiskManager` $\to$ `SimulatedBroker` $\to$ `PaperPortfolio`
   - Verified via static AST scanner (`backend/tests/test_no_brokerage_imports.py`). No imports or references to live brokerage execution SDKs exist.
2. **Credential Sanitization**:
   - Zero API secrets, tokens, or credentials are stored in logs, source code, or exported reports.
3. **Container Isolation**:
   - Docker container runs under an unprivileged `appuser` (UID 10001) with read-only root options and non-network health checks.
4. **Clean Failure Fallbacks**:
   - In `REAL_TIME` mode, missing credentials transition cleanly to `NOT_CONFIGURED` without fallback to fake data.
