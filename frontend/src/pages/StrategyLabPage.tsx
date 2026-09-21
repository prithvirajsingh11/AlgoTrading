import React, { useState, useEffect } from "react";
import { listStrategies } from "../services/strategies";
import { listDatasets } from "../services/datasets";
import { createAndRunExperiment, compareExperiments } from "../services/experiments";
import { StrategyMetadata, DatasetMetadata, ProviderComparisonResult, ExperimentResult } from "../types";
import { LoadingSpinner, ErrorMessage, StatusBadge, MetricsGrid } from "../components/Common";
import { Play, GitCompare, Cpu } from "lucide-react";

export const StrategyLabPage: React.FC = () => {
  const [strategies, setStrategies] = useState<StrategyMetadata[]>([]);
  const [datasets, setDatasets] = useState<DatasetMetadata[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Active Strategy selection
  const [selectedStrategyId, setSelectedStrategyId] = useState<string>("MovingAverageCross");
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("AAPL");
  const [params, setParams] = useState<Record<string, number | string | boolean>>({});

  // Single experiment run state
  const [singleRunning, setSingleRunning] = useState(false);
  const [singleResult, setSingleResult] = useState<ExperimentResult | null>(null);

  // Compare strategies state
  const [comparing, setComparing] = useState(false);
  const [comparisonResult, setComparisonResult] = useState<ProviderComparisonResult | null>(null);

  const init = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sList, dList] = await Promise.all([listStrategies(), listDatasets()]);
      const validStrats = sList.filter((s) => s.id !== "Jev");
      setStrategies(validStrats);
      setDatasets(dList);
      if (validStrats.length > 0) {
        setSelectedStrategyId(validStrats[0].id);
        const defaults: Record<string, number | string | boolean> = {};
        validStrats[0].parameters.forEach((p) => {
          defaults[p.name] = p.default;
        });
        setParams(defaults);
      }
      if (dList.length > 0) {
        setSelectedDatasetId(dList[0].dataset_id);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    init();
  }, []);

  const handleSelectStrategy = (stratId: string) => {
    setSelectedStrategyId(stratId);
    const strat = strategies.find((s) => s.id === stratId);
    if (strat) {
      const defaults: Record<string, number | string | boolean> = {};
      strat.parameters.forEach((p) => {
        defaults[p.name] = p.default;
      });
      setParams(defaults);
    }
  };

  const handleRunSingle = async () => {
    setSingleRunning(true);
    setError(null);
    setComparisonResult(null);

    const ds = datasets.find((d) => d.dataset_id === selectedDatasetId);
    const symbols = ds ? ds.symbols : [selectedDatasetId];

    try {
      const res = await createAndRunExperiment({
        dataset: { dataset_id: selectedDatasetId, symbols, timeframe: ds?.timeframe || "1d" },
        strategy: { name: selectedStrategyId, parameters: params },
        portfolio: { initial_capital: 100000 },
        execution: { commission_fixed: 1.0, commission_percent: 0.0005, slippage_bps: 5.0 },
        risk: {
          max_position_pct: 0.5,
          max_drawdown_limit: 0.3,
          allow_shorting: selectedStrategyId === "PairsTrading",
          position_sizing_method: "percent_equity",
          position_size_pct: 0.2,
          risk_per_trade: 0.02,
        },
        seed: 42,
      });
      setSingleResult(res);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSingleRunning(false);
    }
  };

  const handleCompareAll = async () => {
    setComparing(true);
    setError(null);
    setSingleResult(null);

    const ds = datasets.find((d) => d.dataset_id === selectedDatasetId);
    const symbols = ds ? ds.symbols : [selectedDatasetId];

    try {
      // Run each core strategy on the dataset
      const targetStrategies = ["MovingAverageCross", "TimeSeriesMomentum", "MeanReversion"];
      const expIds: string[] = [];

      for (const stratName of targetStrategies) {
        const stratMeta = strategies.find((s) => s.id === stratName);
        const stratParams: Record<string, number | string | boolean> = {};
        stratMeta?.parameters.forEach((p) => {
          stratParams[p.name] = p.default;
        });

        const res = await createAndRunExperiment({
          dataset: { dataset_id: selectedDatasetId, symbols, timeframe: ds?.timeframe || "1d" },
          strategy: { name: stratName, parameters: stratParams },
          portfolio: { initial_capital: 100000 },
          execution: { commission_fixed: 1.0, commission_percent: 0.0005, slippage_bps: 5.0 },
          risk: {
            max_position_pct: 0.5,
            max_drawdown_limit: 0.3,
            allow_shorting: false,
            position_sizing_method: "percent_equity",
            position_size_pct: 0.2,
            risk_per_trade: 0.02,
          },
          seed: 42,
        });
        expIds.push(res.experiment_id);
      }

      // Call backend compare endpoint
      const comp = await compareExperiments(expIds);
      setComparisonResult(comp);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setComparing(false);
    }
  };

  if (loading) return <LoadingSpinner message="Loading Strategy Lab..." />;
  if (error && !singleResult && !comparisonResult) return <ErrorMessage message={error} onRetry={init} />;

  const currentStrat = strategies.find((s) => s.id === selectedStrategyId);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <div>
        <h1 style={{ fontSize: "1.25rem", fontWeight: 700, letterSpacing: "-0.01em" }}>
          Strategy Research Lab
        </h1>
        <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
          Quantitative exploration across Momentum, Mean Reversion, Moving Averages, and Pairs Trading
        </p>
      </div>

      {/* Strategy Selector Tabs */}
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", borderBottom: "1px solid var(--border-subtle)", paddingBottom: "0.5rem" }}>
        {strategies.map((s) => {
          const isSelected = s.id === selectedStrategyId;
          return (
            <button
              key={s.id}
              onClick={() => handleSelectStrategy(s.id)}
              className="btn btn-secondary btn-sm"
              style={{
                backgroundColor: isSelected ? "var(--accent-blue)" : "var(--bg-surface)",
                color: isSelected ? "#FFF" : "var(--text-secondary)",
                borderColor: isSelected ? "var(--accent-blue)" : "var(--border-strong)",
                fontWeight: isSelected ? 600 : 400,
              }}
            >
              <Cpu size={14} /> {s.name}
            </button>
          );
        })}
      </div>

      {/* Selected Strategy Workbench */}
      {currentStrat && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1rem" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.25rem" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: 700 }}>{currentStrat.name}</h2>
                <StatusBadge status={currentStrat.category} variant="blue" />
              </div>
              <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>{currentStrat.description}</p>
            </div>

            {/* Target Dataset Selection */}
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.8125rem" }}>
              <span style={{ color: "var(--text-muted)" }}>Benchmark Dataset:</span>
              <select value={selectedDatasetId} onChange={(e) => setSelectedDatasetId(e.target.value)}>
                {datasets.map((d) => (
                  <option key={d.dataset_id} value={d.dataset_id}>
                    {d.dataset_id} ({d.row_count} bars)
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Parameters Input */}
          <div style={{ padding: "1rem", backgroundColor: "var(--bg-app)", borderRadius: "4px", border: "1px solid var(--border-subtle)", marginBottom: "1rem" }}>
            <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "0.5rem" }}>
              Active Strategy Parameters
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "1rem" }}>
              {currentStrat.parameters.map((p) => (
                <div key={p.name}>
                  <label style={{ display: "block", fontSize: "0.7rem", color: "var(--text-secondary)", marginBottom: "0.25rem" }}>
                    {p.name}
                  </label>
                  <input
                    type={p.type === "int" || p.type === "float" ? "number" : "text"}
                    value={params[p.name] !== undefined ? String(params[p.name]) : String(p.default)}
                    onChange={(e) =>
                      setParams((prev) => ({
                        ...prev,
                        [p.name]: p.type === "int" ? parseInt(e.target.value, 10) || 0 : p.type === "float" ? parseFloat(e.target.value) || 0.0 : e.target.value,
                      }))
                    }
                    step={p.type === "float" ? "0.01" : "1"}
                    style={{ width: "100%" }}
                  />
                </div>
              ))}
            </div>
          </div>

          {/* Action Buttons */}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: "1rem" }}>
            <button onClick={handleRunSingle} disabled={singleRunning || comparing} className="btn btn-primary">
              <Play size={16} /> RUN EXPERIMENT
            </button>
            <button onClick={handleCompareAll} disabled={singleRunning || comparing} className="btn btn-secondary">
              <GitCompare size={16} /> COMPARE STRATEGIES
            </button>
          </div>
        </div>
      )}

      {/* Loading States */}
      {singleRunning && <LoadingSpinner message="Executing quantitative experiment..." />}
      {comparing && <LoadingSpinner message="Evaluating multi-strategy comparison benchmark on backend..." />}
      {error && <ErrorMessage message={error} />}

      {/* Single Run Result */}
      {singleResult && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1.25rem", borderRadius: "4px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <h3 style={{ fontSize: "1rem", fontWeight: 700 }}>
              Experiment Result: {singleResult.experiment_id} ({singleResult.strategy_info.name})
            </h3>
            <span className="mono" style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
              Hash: {singleResult.configuration_hash}
            </span>
          </div>
          <MetricsGrid metrics={singleResult.metrics} />
        </div>
      )}

      {/* Multi-Strategy Comparison Table */}
      {comparisonResult && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1.25rem", borderRadius: "4px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <h3 style={{ fontSize: "1rem", fontWeight: 700 }}>
              Multi-Strategy Comparison Matrix ({comparisonResult.count} Strategies)
            </h3>
            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
              Backend Multi-Strategy Comparison Service · Zero Frontend Ranking Scores
            </span>
          </div>

          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Strategy</th>
                  <th>Category</th>
                  <th>Total Return</th>
                  <th>CAGR</th>
                  <th>Sharpe</th>
                  <th>Sortino</th>
                  <th>Max DD</th>
                  <th>Win Rate</th>
                  <th>Profit Factor</th>
                  <th>Trades</th>
                </tr>
              </thead>
              <tbody>
                {comparisonResult.comparisons.map((c) => {
                  const m = c.trading_metrics;
                  const isPos = m.total_return_pct >= 0;
                  return (
                    <tr key={c.experiment_id}>
                      <td style={{ fontWeight: 600 }}>{c.strategy_name}</td>
                      <td>
                        <StatusBadge status={c.category} variant="blue" />
                      </td>
                      <td className="mono" style={{ color: isPos ? "var(--status-green)" : "var(--status-red)", fontWeight: 600 }}>
                        {isPos ? "+" : ""}{(m.total_return_pct * 100).toFixed(2)}%
                      </td>
                      <td className="mono">{(m.cagr * 100).toFixed(2)}%</td>
                      <td className="mono">{m.sharpe_ratio != null ? m.sharpe_ratio.toFixed(2) : "N/A"}</td>
                      <td className="mono">{m.sortino_ratio != null ? m.sortino_ratio.toFixed(2) : "N/A"}</td>
                      <td className="mono" style={{ color: "var(--status-red)" }}>-{(m.max_drawdown_pct * 100).toFixed(2)}%</td>
                      <td className="mono">{(m.win_rate * 100).toFixed(1)}%</td>
                      <td className="mono">{m.profit_factor != null ? m.profit_factor.toFixed(2) : "N/A"}</td>
                      <td className="mono">{m.total_trades}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
