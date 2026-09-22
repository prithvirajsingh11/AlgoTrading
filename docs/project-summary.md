# AlgoTrade v1.0.0 — Technical Project Summary

> **SIMULATION / RESEARCH PLATFORM — NOT REAL-MONEY TRADING SOFTWARE**
> AlgoTrade is a portfolio-ready algorithmic-trading research and paper-trading platform built with production-oriented engineering practices. It contains zero live-money trading endpoints and executes zero real monetary exchange transactions. All trading is strictly simulated via `SimulatedBroker`.

---

## 1. Overview & System Scope

**AlgoTrade** is a portfolio-ready algorithmic-trading research and paper-trading platform featuring:
- **Event-driven backtesting** with strict zero-lookahead bias guarantees.
- **Multiple quantitative strategies** (Moving Average Crossover, Time-Series Momentum, Mean Reversion).
- **Multi-asset pairs trading** with dynamic rolling OLS hedge ratio and atomic dual-leg execution.
- **Reproducible experiments** with deterministic SHA-256 configuration hashes.
- **Walk-forward evaluation** with quarantined out-of-sample test splits.
- **XGBoost ML** with purged time-series cross-validation and feature schema verification.
- **Jev AI advisory decision layer** with structured market context packaging, deterministic caching, and graceful fallbacks.
- **Real-time market-data ingestion** supporting vendor-agnostic streaming adapters.
- **Synthetic and historical modes** alongside real-time data streaming.
- **Paper trading** with tick-to-bar aggregation and crash recovery.
- **Risk management** with authoritative pre-trade checks (cash, concentration, drawdown).
- **WebSockets** with asynchronous backpressure protection and live broadcasting.
- **REST APIs** built on FastAPI with Pydantic v2 schemas and correlation IDs.
- **Persistence** using SQLite with Write-Ahead Logging (WAL) and double-entry accounting.
- **Observability** with structured JSON logging and sanitized error responses.
- **CI/CD** automated via GitHub Actions.
- **Docker** containerization running under an unprivileged `appuser`.
- **Automated testing** with high test coverage across backend and frontend.

---

## 2. Core Architecture & System Layers

AlgoTrade is architected as an event-driven, decoupled system consisting of:
- **Core Engine (Python 3.11+)**: Discrete-event backtester and paper trading engine utilizing domain-driven design (`SimulatedBroker`, `Portfolio`, `RiskManager`, `Strategy`).
- **REST & Streaming API (FastAPI + Pydantic v2)**: Non-blocking asynchronous REST endpoints and low-latency WebSocket broadcaster with backpressure protection.
- **Persistence Store (SQLite / aiosqlite)**: Double-entry ledger with Write-Ahead Logging (WAL) and crash-recovery state hydration.
- **Frontend Console (React 18 + TypeScript + Vite)**: Modular, code-split dashboard (171 KB core) with runtime `<ErrorBoundary>` protection and Recharts performance blotters.

---

## 3. Quantitative Strategies & Statistical Arbitrage
- **Moving Average Crossover**: Fast/slow exponential and simple moving average cross with configurable lookback windows.
- **Time-Series Momentum**: Rolling return lookback evaluation with dual entry/exit threshold gates and trailing stop protection.
- **Mean Reversion**: Rolling Bollinger Band z-score calculations ($Z = \frac{P - \mu}{\sigma}$) with dynamic overbought/oversold boundaries.
- **Multi-Asset Statistical Arbitrage (Pairs Trading)**: Cointegration-based statistical arbitrage between synchronized asset pairs (e.g. AAPL/MSFT). Calculates rolling OLS hedge ratio $\beta = \frac{\text{Cov}(P_1, P_2)}{\text{Var}(P_2)}$ dynamically and executes atomic simultaneous two-leg trades.

---

## 4. Quantitative Research & Reproducibility Engine
- **Walk-Forward Analysis**: Non-overlapping sliding windows ($Train \to Test \to Shift$) quarantining out-of-sample periods to prevent overfitting.
- **Parameter Sweeps**: Grid search engine bounded by resource limiters (`max_sweep_combinations = 1,000`).
- **Cryptographic Reproducibility**: Every experiment computes a deterministic SHA-256 configuration hash capturing dataset metadata, strategy parameters, execution mechanics, and risk settings.

---

## 5. Supervised Machine Learning (XGBoost)
- **Time-Aware Splitting**: Strict chronological purged cross-validation (60% Train, 20% Val, 20% Test) ensuring test sets remain completely untouched during feature scaling and training.
- **Multi-Horizon Return Prediction**: Predicts directional probability for next-$k$ bar forward returns.
- **Cryptographic Model Artifacts**: Model weights, feature orderings, and feature schema hashes (SHA-256) serialized together. Any query with mismatched column ordering or schema variance is rejected.
- **Classification vs Trading Performance**: Classification Performance (Accuracy, ROC-AUC, F1, Log Loss) is strictly distinguished from Trading Performance (Sharpe, Drawdown, Profit Factor). High classification accuracy does not imply trading profitability.

---

## 6. Jev AI Advisory Decision Layer
- **Advisory Role**: Operates strictly as an advisory overlay on top of quantitative strategies, never as a guaranteed predictor, profitable trading oracle, or autonomous live trader.
- **Context Packaging**: Packages point-in-time technical features, portfolio metrics, and market regime into a structured, zero-lookahead JSON payload.
- **Deterministic SHA-256 Cache**: Identical quantitative market states hit local in-memory cache, bypassing network calls and eliminating duplicate evaluation latency.
- **Modes**:
  - `MOCK / TEST PROVIDER`: Used for deterministic offline tests and demonstrations.
  - `CACHED_JEV`: Replays cached decisions matching input context hash.
  - `LIVE_JEV`: Live advisory queries via secure external API.
- **Graceful Fail-Safe Fallback**: Any HTTP error, timeout, or JSON parse failure safely defaults to `NO_ACTION`, preserving deterministic rule execution.

---

## 7. Real-Time Market Data & Multi-Asset Synchronization
- **Vendor-Agnostic Abstraction**: `RealTimeMarketDataProvider` interface supporting `InMemoryStreamingAdapter` (synthetic test feed) and `AlpacaMarketDataAdapter` (WebSocket v2 IEX/SIP feeds).
- **Tick-to-Bar Aggregation (`TickToBarAggregator`)**: Real-time tick aggregation into standard OHLCV bars across configurable intervals with boundary alignment and auto-rollover.
- **Multi-Asset Synchronization (`MultiAssetSynchronizer`)**: Cross-symbol temporal freshness tracking. Quarantines desynchronized pairs exceeding `max_desync_seconds` to prevent synthetic statistical arbitrage races.
- **$O(1)$ Incremental Feature Engine (`StreamingFeatureEngine`)**: Memory-bounded ring buffers (`collections.deque(maxlen=150)`) calculating rolling indicators incrementally.

---

## 8. Paper Trading & Three Operating Modes
- **Three Isolated Operational Modes**:
  1. `HISTORICAL_REPLAY`: Deterministic historical bar-by-bar simulation.
  2. `SYNTHETIC_STREAM`: High-frequency random-walk feed explicitly badged `[SYNTHETIC TEST FEED]`.
  3. `REAL_TIME`: Live exchange market data streaming; unconfigured credentials cleanly transition to `NOT_CONFIGURED` without fake data or unauthorized network probes.
- **Crash Recovery & Hydration**: On server restart, active `RUNNING` sessions safely hydrate to `PAUSED` with an audit notice, preventing ghost order generation or double execution.
- **WebSocket Backpressure Protection**: 100ms asynchronous timeout per subscriber automatically unregisters stalled clients without blocking the tick engine.

---

## 9. Authoritative Risk Management & Safety Invariants
- **Pre-Trade Risk Gate**: All strategy and ML signals must pass through the authoritative `RiskManager` before order placement:
  - Single-asset position concentration limiter.
  - Portfolio peak-to-trough drawdown circuit breaker.
  - Cash adequacy verification against current market price.
- **Signal Safety State Machine**:
  - `CONNECTED` + fresh data $\longrightarrow$ `SIGNALS_ENABLED`.
  - `STALE`, `DISCONNECTED`, or `ERROR` $\longrightarrow$ `SIGNALS_PAUSED` (entry signals suppressed).
- **Asymmetric Capital Protection**: When signals are paused, existing stop-loss orders remain 100% active against incoming quote ticks, ensuring capital protection during network degradation.
- **AST Paper-Only Invariant**: Static AST scanner continuously verifies that zero live brokerage SDKs or live exchange endpoints exist across the codebase. All orders route strictly to `SimulatedBroker`.

---

## 10. Performance Benchmarks

Measured as a **local synthetic software-performance benchmark on deterministic GBM datasets in the development environment**:

Benchmark results do **NOT** represent exchange latency, brokerage execution latency, production infrastructure performance, trading profitability, or investment performance. Zero claims of trading profitability are made.

The benchmark engine measures 7 subsystems:
1. **Dataset ingestion**: 123,047 bars/sec.
2. **Streaming feature engine**: 18.7 µs/bar ($O(1)$ ring buffer).
3. **Strategy signal generation**: 12.4 µs/bar.
4. **Event-driven backtesting**: 2,418 bars/sec.
5. **Paper-step replay**: 1,120 µs/step.
6. **WebSocket serialization**: 18,450 msgs/sec.
7. **Peak memory allocation**: 0.84 MB allocation delta over continuous 5,000-bar processing.

---

## 11. Testing & Code Quality Assurance
- **Backend Tests**: 229 passed, 1 skipped, 0 failures across automated pytest suites covering event pipelines, failure modes, memory bounds, concurrency, and security.
- **Frontend Tests**: 11 passed, 0 failures across Vitest contract tests verifying mode separation and decision attribution blotters.
- **Code Splitting**: Dynamic route loading producing a 171 KB core production bundle.
- **Docker**: Multi-stage unprivileged `appuser` container with built-in non-network health probes.
- **10-Stage Offline Demo**: Fully deterministic end-to-end demonstration running offline via `python -m backend.app.cli demo`.
