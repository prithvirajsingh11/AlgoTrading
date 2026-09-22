# Quantitative Research Experiment Report: `exp_8bf3f6e37872`

> **SIMULATION / RESEARCH PLATFORM — NOT REAL-MONEY TRADING SOFTWARE**: This experiment was executed within AlgoTrade's discrete-event simulation engine. All trades are simulated with modeled transaction costs and zero lookahead bias. Zero live brokerage connections or real monetary orders.

## 1. Experiment Overview & Reproducibility

- **Experiment ID**: `exp_8bf3f6e37872`
- **Reproducibility Hash (SHA-256)**: `8bf3f6e378725adc167504e825fb12de3db09aa89118139df957bf9297f1283c`
- **Execution Date**: `2026-09-22T19:13:42.018489+00:00`
- **Runtime**: `624.68 ms`
- **Total Bars Processed**: `5000`

## 2. Research Configuration & Execution Assumptions

### Dataset & Strategy
- **Dataset**: `benchmark_single_asset`
- **Symbols**: `AAPL`
- **Strategy**: `TimeSeriesMomentum`
- **Parameters**: `{"lookback_period": 20, "holding_period": 5}`

### Portfolio & Execution Mechanics
- **Initial Capital**: `$100,000.00`
- **Fixed Commission**: `$1.00` per fill
- **Percentage Commission**: `5.0 bps`
- **Execution Slippage**: `5.0 bps`

### Risk & Concentration Limits
- **Position Sizing**: `25.0% of equity`
- **Maximum Concentration**: `50.0%`
- **Max Drawdown Circuit Breaker**: `25.0%`

## 3. Quantitative Performance Metrics

| Metric | Value |
| :--- | :--- |
| **Total Return** | `-7.66%` |
| **Annualized Return** | `-0.40%` |
| **Sharpe Ratio** | `-0.5589` |
| **Sortino Ratio** | `-0.7727` |
| **Max Drawdown** | `18.88%` |
| **Win Rate** | `30.47%` |
| **Profit Factor** | `0.87` |
| **Executed Trades** | `128` |

## 4. Trade Execution Blotter Summary

| Timestamp | Symbol | Side | Quantity | Price | P&L |
| :--- | :--- | :--- | :--- | :--- | :--- |
|  | AAPL | BUY | 167.0 | $0.00 | $-114.25 |
|  | AAPL | BUY | 162.0 | $0.00 | $-100.90 |
|  | AAPL | BUY | 157.0 | $0.00 | $+681.21 |
|  | AAPL | BUY | 170.0 | $0.00 | $-1315.63 |
|  | AAPL | BUY | 170.0 | $0.00 | $-933.00 |
|  | AAPL | BUY | 172.0 | $0.00 | $-237.12 |
|  | AAPL | BUY | 185.0 | $0.00 | $-1261.71 |
|  | AAPL | BUY | 187.0 | $0.00 | $-857.84 |
|  | AAPL | BUY | 198.0 | $0.00 | $-1636.38 |
|  | AAPL | BUY | 214.0 | $0.00 | $-763.91 |
|  | AAPL | BUY | 211.0 | $0.00 | $-740.86 |
|  | AAPL | BUY | 217.0 | $0.00 | $+578.97 |
|  | AAPL | BUY | 207.0 | $0.00 | $-301.78 |
|  | AAPL | BUY | 204.0 | $0.00 | $+178.65 |
|  | AAPL | BUY | 192.0 | $0.00 | $-1170.84 |

*(Truncated: 128 total trades)*
