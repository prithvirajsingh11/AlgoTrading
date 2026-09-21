import React, { useState, useEffect } from "react";
import { listDatasets } from "../services/datasets";
import { listStrategies } from "../services/strategies";
import { createAndRunExperiment } from "../services/experiments";
import { getHistoricalBars } from "../services/backtests";
import { DatasetMetadata, StrategyMetadata, ExperimentResult, OHLCVBar } from "../types";
import { LoadingSpinner, ErrorMessage, MetricsGrid, TradeHistoryTable, StatusBadge } from "../components/Common";
import { CandlestickChart } from "../charts/CandlestickChart";
import { EquityDrawdownChart } from "../charts/EquityDrawdownChart";
import { Play, Sliders, Sparkles } from "lucide-react";

export const BacktestPage: React.FC = () => {
  const [datasets, setDatasets] = useState<DatasetMetadata[]>([]);
  const [strategies, setStrategies] = useState<StrategyMetadata[]>([]);
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [initError, setInitError] = useState<string | null>(null);

  // Form states
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("AAPL");
  const [selectedStrategyId, setSelectedStrategyId] = useState<string>("MovingAverageCross");
  const [strategyParams, setStrategyParams] = useState<Record<string, number | string | boolean>>({
    fast_period: 10,
    slow_period: 30,
  });

  const [initialCapital, setInitialCapital] = useState<number>(100000);
  const [commissionFixed, setCommissionFixed] = useState<number>(1.0);
  const [commissionPct, setCommissionPct] = useState<number>(0.0005);
  const [slippageBps, setSlippageBps] = useState<number>(5.0);
  const [positionSizePct, setPositionSizePct] = useState<number>(0.20);
  const [maxPositionPct, setMaxPositionPct] = useState<number>(0.50);
  const [maxDrawdownLimit, setMaxDrawdownLimit] = useState<number>(0.30);

  // Advisory toggles
  const [jevEnabled, setJevEnabled] = useState<boolean>(false);
  const [jevMinConfidence, setJevMinConfidence] = useState<number>(0.70);

  // Execution state
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [result, setResult] = useState<ExperimentResult | null>(null);
  const [historicalBars, setHistoricalBars] = useState<OHLCVBar[]>([]);

  useEffect(() => {
    const init = async () => {
      setLoadingInitial(true);
      setInitError(null);
      try {
        const [dList, sList] = await Promise.all([listDatasets(), listStrategies()]);
        setDatasets(dList);
        setStrategies(sList);
        if (dList.length > 0) {
          setSelectedDatasetId(dList[0].dataset_id);
        }
      } catch (err) {
        setInitError((err as Error).message);
      } finally {
        setLoadingInitial(false);
      }
    };
    init();
  }, []);

  // When strategy changes, initialize default parameters
  const handleStrategyChange = (stratId: string) => {
    setSelectedStrategyId(stratId);
    const strat = strategies.find((s) => s.id === stratId);
    if (strat) {
      const defaults: Record<string, number | string | boolean> = {};
      strat.parameters.forEach((p) => {
        defaults[p.name] = p.default;
      });
      setStrategyParams(defaults);
    }
  };

  const handleParamChange = (name: string, value: string, type: string) => {
    setStrategyParams((prev) => ({
      ...prev,
      [name]: type === "int" ? parseInt(value, 10) || 0 : type === "float" ? parseFloat(value) || 0.0 : value,
    }));
  };

  const handleRunBacktest = async (e: React.FormEvent) => {
    e.preventDefault();
    setRunning(true);
    setRunError(null);

    const activeDataset = datasets.find((d) => d.dataset_id === selectedDatasetId);
    const symbols = activeDataset ? activeDataset.symbols : [selectedDatasetId];

    const configPayload = {
      dataset: {
        dataset_id: selectedDatasetId,
        symbols,
        timeframe: activeDataset?.timeframe || "1d",
      },
      strategy: {
        name: selectedStrategyId,
        parameters: strategyParams,
      },
      execution: {
        commission_fixed: commissionFixed,
        commission_percent: commissionPct,
        slippage_bps: slippageBps,
      },
      risk: {
        max_position_pct: maxPositionPct,
        max_drawdown_limit: maxDrawdownLimit,
        allow_shorting: selectedStrategyId === "PairsTrading",
        position_sizing_method: "percent_equity",
        position_size_pct: positionSizePct,
        risk_per_trade: 0.02,
      },
      portfolio: {
        initial_capital: initialCapital,
      },
      seed: 42,
      jev: jevEnabled
        ? {
            enabled: true,
            min_confidence: jevMinConfidence,
            cache_enabled: true,
          }
        : undefined,
    };

    try {
      const expResult = await createAndRunExperiment(configPayload);
      setResult(expResult);

      // Fetch corresponding OHLCV bars for the Candlestick chart
      try {
        const bars = await getHistoricalBars(symbols[0], 250);
        setHistoricalBars(bars);
      } catch {
        // bars optional
      }
    } catch (err) {
      setRunError((err as Error).message);
    } finally {
      setRunning(false);
    }
  };

  if (loadingInitial) return <LoadingSpinner message="Loading datasets and strategies..." />;
  if (initError) return <ErrorMessage message={initError} />;

  const currentStrat = strategies.find((s) => s.id === selectedStrategyId);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: "1.25rem", fontWeight: 700, letterSpacing: "-0.01em" }}>
          Backtest Lab
        </h1>
        <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
          Configure, parameterize, and execute authoritative backtests against historical data
        </p>
      </div>

      {/* Main Control Panel */}
      <form onSubmit={handleRunBacktest} style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "1.25rem", marginBottom: "1.25rem" }}>
          {/* Dataset & Symbol */}
          <div>
            <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.35rem", textTransform: "uppercase" }}>
              Dataset / Asset
            </label>
            <select
              value={selectedDatasetId}
              onChange={(e) => setSelectedDatasetId(e.target.value)}
              style={{ width: "100%" }}
            >
              {datasets.map((d) => (
                <option key={d.dataset_id} value={d.dataset_id}>
                  {d.dataset_id} ({d.symbols.join(", ")}) — {d.row_count} rows [{d.timeframe}]
                </option>
              ))}
            </select>
          </div>

          {/* Strategy Selection */}
          <div>
            <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.35rem", textTransform: "uppercase" }}>
              Strategy
            </label>
            <select
              value={selectedStrategyId}
              onChange={(e) => handleStrategyChange(e.target.value)}
              style={{ width: "100%" }}
            >
              {strategies
                .filter((s) => s.status === "ACTIVE" && s.id !== "Jev")
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.category})
                  </option>
                ))}
            </select>
          </div>

          {/* Initial Capital */}
          <div>
            <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.35rem", textTransform: "uppercase" }}>
              Initial Capital ($)
            </label>
            <input
              type="number"
              value={initialCapital}
              onChange={(e) => setInitialCapital(Number(e.target.value))}
              min={1000}
              step={1000}
              style={{ width: "100%" }}
            />
          </div>

          {/* Position Sizing % */}
          <div>
            <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.35rem", textTransform: "uppercase" }}>
              Position Size (% Equity)
            </label>
            <input
              type="number"
              value={positionSizePct}
              onChange={(e) => setPositionSizePct(Number(e.target.value))}
              min={0.01}
              max={1.0}
              step={0.05}
              style={{ width: "100%" }}
            />
          </div>
        </div>

        {/* Dynamic Strategy Parameters */}
        {currentStrat && currentStrat.parameters.length > 0 && (
          <div style={{ padding: "1rem", backgroundColor: "var(--bg-app)", borderRadius: "4px", border: "1px solid var(--border-subtle)", marginBottom: "1.25rem" }}>
            <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--accent-blue)", marginBottom: "0.75rem", textTransform: "uppercase", display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <Sliders size={14} /> Strategy Parameters: {currentStrat.name}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "1rem" }}>
              {currentStrat.parameters.map((p) => (
                <div key={p.name}>
                  <label style={{ display: "block", fontSize: "0.7rem", color: "var(--text-secondary)", marginBottom: "0.25rem" }}>
                    {p.name} {p.description ? `(${p.description})` : ""}
                  </label>
                  <input
                    type={p.type === "int" || p.type === "float" ? "number" : "text"}
                    value={strategyParams[p.name] !== undefined ? String(strategyParams[p.name]) : String(p.default)}
                    onChange={(e) => handleParamChange(p.name, e.target.value, p.type)}
                    step={p.type === "float" ? "0.01" : "1"}
                    style={{ width: "100%" }}
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Risk & Execution Invariants */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "1rem", marginBottom: "1.25rem", fontSize: "0.75rem" }}>
          <div>
            <label style={{ display: "block", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Fixed Comm ($)</label>
            <input type="number" value={commissionFixed} onChange={(e) => setCommissionFixed(Number(e.target.value))} min={0} step={0.5} style={{ width: "100%" }} />
          </div>
          <div>
            <label style={{ display: "block", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Comm Rate (e.g. 0.0005)</label>
            <input type="number" value={commissionPct} onChange={(e) => setCommissionPct(Number(e.target.value))} min={0} step={0.0001} style={{ width: "100%" }} />
          </div>
          <div>
            <label style={{ display: "block", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Slippage (bps)</label>
            <input type="number" value={slippageBps} onChange={(e) => setSlippageBps(Number(e.target.value))} min={0} step={1} style={{ width: "100%" }} />
          </div>
          <div>
            <label style={{ display: "block", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Max Drawdown Limit</label>
            <input type="number" value={maxDrawdownLimit} onChange={(e) => setMaxDrawdownLimit(Number(e.target.value))} min={0.05} max={0.5} step={0.05} style={{ width: "100%" }} />
          </div>
          <div>
            <label style={{ display: "block", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Max Position Limit</label>
            <input type="number" value={maxPositionPct} onChange={(e) => setMaxPositionPct(Number(e.target.value))} min={0.1} max={1.0} step={0.05} style={{ width: "100%" }} />
          </div>
        </div>

        {/* Jev Advisory Overlay */}
        <div style={{ padding: "0.85rem", backgroundColor: jevEnabled ? "rgba(59, 130, 246, 0.06)" : "transparent", border: "1px solid var(--border-subtle)", borderRadius: "4px", marginBottom: "1.25rem" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer", fontSize: "0.8125rem", fontWeight: 600 }}>
              <input type="checkbox" checked={jevEnabled} onChange={(e) => setJevEnabled(e.target.checked)} />
              <Sparkles size={16} style={{ color: "var(--accent-blue)" }} />
              Enable Jev AI Decision Advisory Overlay
            </label>
            {jevEnabled && (
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "0.75rem" }}>
                <span>Min Confidence:</span>
                <input
                  type="number"
                  value={jevMinConfidence}
                  onChange={(e) => setJevMinConfidence(Number(e.target.value))}
                  min={0.5}
                  max={0.95}
                  step={0.05}
                  style={{ width: "70px" }}
                />
              </div>
            )}
          </div>
        </div>

        {/* Action Button */}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem" }}>
          <button type="submit" disabled={running} className="btn btn-primary" style={{ minWidth: "160px" }}>
            {running ? <LoadingSpinner message="Running Backtest..." /> : <><Play size={16} /> RUN BACKTEST</>}
          </button>
        </div>
      </form>

      {/* Error Output */}
      {runError && <ErrorMessage message={runError} />}

      {/* Backtest Results Area */}
      {result && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {/* Result Overview Header */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
                <h2 style={{ fontSize: "1rem", fontWeight: 700 }}>
                  Backtest Result: {result.experiment_id}
                </h2>
                <StatusBadge status="COMPLETED" variant="green" />
                {result.ai_decision_stats && (
                  <span className="badge badge-blue">JEV ASSISTED</span>
                )}
              </div>
              <div className="mono" style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                Config Hash: {result.configuration_hash} · Runtime: {result.execution_statistics?.runtime_ms}ms · Bars: {result.execution_statistics?.total_bars}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Completed At</div>
              <div className="mono" style={{ fontSize: "0.75rem" }}>{result.completed_at.slice(0, 19).replace("T", " ")}</div>
            </div>
          </div>

          {/* Performance Metrics Grid */}
          <MetricsGrid metrics={result.metrics} />

          {/* Interactive Candlestick Chart */}
          {historicalBars.length > 0 && (
            <div>
              <h3 style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: "0.5rem" }}>
                Market OHLCV &amp; Trade Markers ({historicalBars.length} Bars)
              </h3>
              <CandlestickChart
                data={historicalBars}
                trades={result.trade_records}
                symbol={selectedDatasetId}
                height={400}
              />
            </div>
          )}

          {/* Equity & Underwater Drawdown Curve */}
          <div>
            <h3 style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: "0.5rem" }}>
              Equity &amp; Drawdown Dynamics
            </h3>
            <EquityDrawdownChart
              equityCurve={result.equity_curve}
              drawdownCurve={result.drawdown_curve}
              initialCapital={result.execution_statistics?.initial_capital || initialCapital}
              height={320}
            />
          </div>

          {/* Trade Execution History */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
              <h3 style={{ fontSize: "0.875rem", fontWeight: 600 }}>
                Trade Execution History ({result.trade_records.length} Trades)
              </h3>
            </div>
            <TradeHistoryTable trades={result.trade_records} />
          </div>

          {/* Execution Statistics Table */}
          <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
            <h4 style={{ fontSize: "0.8125rem", fontWeight: 600, marginBottom: "0.5rem", color: "var(--text-secondary)" }}>
              EXECUTION STATISTICS &amp; REPRODUCIBILITY CONTRACT
            </h4>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.75rem", fontSize: "0.75rem" }} className="mono">
              <div>Total Bars: <strong>{result.execution_statistics?.total_bars}</strong></div>
              <div>Runtime: <strong>{result.execution_statistics?.runtime_ms} ms</strong></div>
              <div>Trade Count: <strong>{result.execution_statistics?.trade_count}</strong></div>
              <div>Seed: <strong>{result.execution_statistics?.seed}</strong></div>
              <div>Fixed Commission: <strong>${result.execution_statistics?.commission_fixed}</strong></div>
              <div>Rate: <strong>{(result.execution_statistics?.commission_percent * 100).toFixed(3)}%</strong></div>
              <div>Slippage: <strong>{result.execution_statistics?.slippage_bps} bps</strong></div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
