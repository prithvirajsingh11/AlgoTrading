import React, { useState, useEffect } from "react";
import { listDatasets } from "../services/datasets";
import { createAndRunExperiment, compareExperiments } from "../services/experiments";
import { DatasetMetadata, ProviderComparisonResult } from "../types";
import { LoadingSpinner, ErrorMessage, StatusBadge } from "../components/Common";
import { GitCompare, Cpu, Sparkles, TrendingUp } from "lucide-react";

export const ComparisonPage: React.FC = () => {
  const [datasets, setDatasets] = useState<DatasetMetadata[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("AAPL");
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [runningComparison, setRunningComparison] = useState(false);
  const [comparisonData, setComparisonData] = useState<ProviderComparisonResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const init = async () => {
      setLoadingInitial(true);
      setError(null);
      try {
        const dList = await listDatasets();
        setDatasets(dList);
        if (dList.length > 0) {
          setSelectedDatasetId(dList[0].dataset_id);
        }
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoadingInitial(false);
      }
    };
    init();
  }, []);

  const handleRunComparativeStudy = async () => {
    setRunningComparison(true);
    setError(null);
    try {
      const activeDataset = datasets.find((d) => d.dataset_id === selectedDatasetId);
      const symbols = activeDataset ? activeDataset.symbols : [selectedDatasetId];
      const tf = activeDataset?.timeframe || "1d";

      const expIds: string[] = [];

      // 1. Traditional Rule-Based Strategy (e.g. Momentum)
      const resTrad = await createAndRunExperiment({
        dataset: { dataset_id: selectedDatasetId, symbols, timeframe: tf },
        strategy: { name: "MovingAverageCross", parameters: { fast_period: 10, slow_period: 30 } },
        portfolio: { initial_capital: 100000 },
        execution: { commission_fixed: 1.0, commission_percent: 0.0005, slippage_bps: 5.0 },
        risk: { max_position_pct: 0.5, max_drawdown_limit: 0.3, allow_shorting: false, position_sizing_method: "percent_equity", position_size_pct: 0.2, risk_per_trade: 0.02 },
        seed: 42,
      });
      expIds.push(resTrad.experiment_id);

      // 2. Machine Learning XGBoost Strategy
      const resML = await createAndRunExperiment({
        dataset: { dataset_id: selectedDatasetId, symbols, timeframe: tf },
        strategy: { name: "MLStrategy", parameters: { buy_threshold: 0.55, sell_threshold: 0.45 } },
        portfolio: { initial_capital: 100000 },
        execution: { commission_fixed: 1.0, commission_percent: 0.0005, slippage_bps: 5.0 },
        risk: { max_position_pct: 0.5, max_drawdown_limit: 0.3, allow_shorting: false, position_sizing_method: "percent_equity", position_size_pct: 0.2, risk_per_trade: 0.02 },
        seed: 42,
        ml: { enabled: true, buy_threshold: 0.55, sell_threshold: 0.45 },
      });
      expIds.push(resML.experiment_id);

      // 3. Jev AI Assisted Strategy
      const resJev = await createAndRunExperiment({
        dataset: { dataset_id: selectedDatasetId, symbols, timeframe: tf },
        strategy: { name: "MovingAverageCross", parameters: { fast_period: 10, slow_period: 30 } },
        portfolio: { initial_capital: 100000 },
        execution: { commission_fixed: 1.0, commission_percent: 0.0005, slippage_bps: 5.0 },
        risk: { max_position_pct: 0.5, max_drawdown_limit: 0.3, allow_shorting: false, position_sizing_method: "percent_equity", position_size_pct: 0.2, risk_per_trade: 0.02 },
        seed: 42,
        jev: { enabled: true, min_confidence: 0.70, cache_enabled: true },
      });
      expIds.push(resJev.experiment_id);

      // Compare across all 3
      const comp = await compareExperiments(expIds);
      setComparisonData(comp);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setRunningComparison(false);
    }
  };

  if (loadingInitial) return <LoadingSpinner message="Loading dataset registry for comparative study..." />;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: "1.25rem", fontWeight: 700, letterSpacing: "-0.01em" }}>
          Model &amp; Decision Provider Comparison
        </h1>
        <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
          Side-by-side evaluation of Traditional Rule-Based vs Supervised XGBoost vs Jev Advisory AI
        </p>
      </div>

      {/* Control Panel */}
      <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <span style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--text-secondary)" }}>Target Benchmark Dataset:</span>
          <select value={selectedDatasetId} onChange={(e) => setSelectedDatasetId(e.target.value)} style={{ minWidth: "200px" }}>
            {datasets.map((d) => (
              <option key={d.dataset_id} value={d.dataset_id}>
                {d.dataset_id} ({d.row_count} bars)
              </option>
            ))}
          </select>
        </div>

        <button onClick={handleRunComparativeStudy} disabled={runningComparison} className="btn btn-primary">
          <GitCompare size={16} /> RUN COMPARATIVE STUDY (3 PROVIDERS)
        </button>
      </div>

      {error && <ErrorMessage message={error} />}
      {runningComparison && <LoadingSpinner message="Executing synchronized comparison across Traditional, ML, and Jev providers..." />}

      {/* Comparison Tables */}
      {comparisonData && (
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          {/* Disclaimer Note */}
          <div style={{ padding: "0.75rem 1rem", backgroundColor: "rgba(59, 130, 246, 0.05)", border: "1px solid var(--border-subtle)", borderRadius: "4px", fontSize: "0.75rem", color: "var(--text-secondary)" }}>
            * Objective Comparative Assessment: No artificial winner scores or arbitrary ranking weightings are applied. Metrics reflect backend execution under identical initial capital ($100k) and risk limits.
          </div>

          {/* Section 1: Trading Performance Metrics */}
          <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem" }}>
            <h2 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "0.75rem", color: "var(--accent-blue)" }}>
              Section 1: Trading &amp; Portfolio Execution Metrics
            </h2>
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Provider Architecture</th>
                    <th>Strategy Name</th>
                    <th>Total Return</th>
                    <th>CAGR</th>
                    <th>Sharpe Ratio</th>
                    <th>Sortino</th>
                    <th>Max Drawdown</th>
                    <th>Win Rate</th>
                    <th>Profit Factor</th>
                    <th>Trades</th>
                  </tr>
                </thead>
                <tbody>
                  {comparisonData.comparisons.map((c) => {
                    const m = c.trading_metrics;
                    const isPos = (m.total_return_pct ?? 0) >= 0;
                    return (
                      <tr key={c.experiment_id}>
                        <td style={{ fontWeight: 600 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                            {c.provider === "typesafe_jev" ? <Sparkles size={14} style={{ color: "var(--accent-blue)" }} /> : c.provider === "xgboost" ? <Cpu size={14} style={{ color: "var(--status-purple)" }} /> : <TrendingUp size={14} />}
                            <span>{c.provider.toUpperCase()}</span>
                          </div>
                        </td>
                        <td>{c.strategy_name}</td>
                        <td className="mono" style={{ color: isPos ? "var(--status-green)" : "var(--status-red)", fontWeight: 700 }}>
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

          {/* Section 2: Prediction / Advisory Decision Metrics */}
          <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem" }}>
            <h2 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "0.75rem", color: "var(--status-purple)" }}>
              Section 2: Prediction &amp; Advisory Decision Metrics (Non-Trading)
            </h2>
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Provider</th>
                    <th>Decision Type</th>
                    <th>Accuracy / Confidence</th>
                    <th>F1 / Brier Score</th>
                    <th>Total Decisions / Predictions</th>
                    <th>Cache / Fallback Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {comparisonData.comparisons.map((c) => {
                    const isJev = c.ai_decision_stats != null;
                    const isML = c.classification_metrics != null;

                    return (
                      <tr key={c.experiment_id}>
                        <td style={{ fontWeight: 600 }}>{c.provider.toUpperCase()}</td>
                        <td>
                          {isJev ? (
                            <StatusBadge status="LLM Advisory Direction" variant="blue" />
                          ) : isML ? (
                            <StatusBadge status="XGBoost Classifier" variant="amber" />
                          ) : (
                            <StatusBadge status="Rule-Based Cross" variant="gray" />
                          )}
                        </td>
                        <td className="mono">
                          {isJev
                            ? `Avg Conf: ${(c.ai_decision_stats!.avg_confidence * 100).toFixed(1)}%`
                            : isML
                            ? `Accuracy: ${(c.classification_metrics!.accuracy * 100).toFixed(1)}%`
                            : "N/A (Deterministic)"}
                        </td>
                        <td className="mono">
                          {isML
                            ? `F1: ${c.classification_metrics!.f1.toFixed(3)} | Brier: ${c.classification_metrics!.brier_score.toFixed(4)}`
                            : isJev
                            ? `Latency: ${c.ai_decision_stats!.avg_latency_ms.toFixed(1)} ms`
                            : "N/A"}
                        </td>
                        <td className="mono">
                          {isJev ? c.ai_decision_stats!.total_decisions : isML ? c.classification_metrics!.support_positive + c.classification_metrics!.support_negative : "-"}
                        </td>
                        <td className="mono">
                          {isJev ? `Hits: ${c.ai_decision_stats!.cache_hits} | Fallbacks: ${c.ai_decision_stats!.fallbacks}` : "-"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
