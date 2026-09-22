# AlgoTrade Platform Engineering & Quantitative Finance Limitations

> **Academic & Institutional Notice**: Quantitative modeling is subject to fundamental mathematical, structural, and practical limitations. AlgoTrade is strictly an educational, scientific research, and simulated paper-trading platform. This document explicitly outlines known modeling assumptions and system boundaries.

---

## 1. Simulation vs. Live Market Execution

| Dimension | AlgoTrade Simulation Modeling | Live Financial Market Reality |
| :--- | :--- | :--- |
| **Order Book Depth** | Point-in-time bid/ask quote ticks with modeled basis-point slippage. | Multi-level Limit Order Book (LOB) with queuing priority, queue cancellation races, and iceberg orders. |
| **Market Impact** | Assumes retail order sizes that do not move market equilibrium. | Large trades cause permanent price impact and temporary adverse liquidity depletion. |
| **Fill Guarantee** | Market orders fill at current quote/bar close + slippage penalty. | Market orders can experience partial fills, quote sweeps, or exchange execution rejections. |
| **Exchange Latency** | Measured in microsecond software execution time on local CPU. | Dominated by WAN routing, fiber transit, network switch hops, TCP stack buffering, and exchange matching engine colocation. |

---

## 2. Granular Technical & Quantitative Limitations

### A. Synthetic Benchmark Datasets
- **Modeling Basis**: The deterministic datasets in `data/demo/` are generated via Geometric Brownian Motion (GBM) with fixed random seeds.
- **Limitation**: Real financial markets exhibit fat-tailed return distributions (excess kurtosis), volatility clustering (heteroskedasticity), macroeconomic regime shifts, and structural breaks that standard GBM does not fully capture.
- **Purpose**: These datasets exist exclusively for deterministic software benchmarking and test reproducibility, not for predicting future market behavior.

### B. OHLCV Bar Aggregation Assumptions
- **Intrabar Path Ambiguity**: When evaluating standard daily or minute OHLCV bars, the discrete-event engine cannot determine the exact intrabar sequence of High vs. Low prices.
- **Handling**: Stop-loss and limit orders are evaluated conservatively against bar High and Low extremes, with overnight gap execution priced at bar Open. In live high-frequency trading, sub-millisecond tick sequencing dictates fill priority.

### C. Tick-to-Bar Aggregation (`BarBuilder`)
- **Boundary Discretization**: Bar aggregation buckets ticks into fixed time intervals (`1s`, `1m`, `5m`, etc.).
- **Limitation**: High-frequency microstructural noise, quote flickering, and exchange timestamp jitter can cause boundary cross discrepancies between disparate data feeds.

### D. Transaction Cost & Slippage Modeling
- **Model**: Fixed dollar commission + percentage fee + configurable basis-point slippage ($\Delta P = P \times \frac{\text{bps}}{10000}$).
- **Limitation**: Live slippage is non-linear and expands dramatically during high-volatility events, macroeconomic news releases (e.g. FOMC, CPI), or off-hours illiquidity.

### E. Machine Learning & Financial Non-Stationarity
- **Methodology**: Supervised XGBoost binary classification predicting multi-horizon directional returns.
- **Limitation**: Financial time series are inherently non-stationary; statistical relationships, autocorrelations, and volatility regimes decay rapidly over time (concept drift).
- **Discipline**: High out-of-sample classification accuracy does not guarantee profitable trading returns once transaction friction, market impact, and timing delays are applied.

### F. Jev Advisory AI Layer External Dependency
- **Integration**: Modular advisory queries routed to TypeSafe SystemOne endpoint.
- **Limitation**: When external networks drop or credentials are unconfigured, Jev advice is unavailable. The platform handles this via an automatic fail-safe fallback to deterministic strategy rules, guaranteeing system availability at the expense of external advisory inputs.

---

## 3. Explicit Non-Claims

To ensure complete institutional transparency, AlgoTrade makes **ZERO** claims regarding:
1. **Trading Profitability**: Past simulated performance in backtests or paper sessions does not indicate future results.
2. **Predictive Accuracy**: Machine learning predictions are probabilistic indicators, not deterministic forecasts.
3. **Exchange Execution Speed**: Software microsecond benchmarks measure local CPU processing time, not live exchange execution latency.
4. **Live Brokerage Readiness**: The platform contains zero live brokerage connections and zero live-money trading paths. All order routing terminates strictly at the internal `SimulatedBroker`.
