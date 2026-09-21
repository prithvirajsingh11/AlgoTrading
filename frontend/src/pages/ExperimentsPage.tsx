import React, { useState, useEffect, useMemo } from "react";
import { listExperiments, getExperiment, rerunExperiment } from "../services/experiments";
import { ExperimentResult } from "../types";
import { LoadingSpinner, ErrorMessage, StatusBadge, EmptyState, MetricsGrid, TradeHistoryTable } from "../components/Common";
import { EquityDrawdownChart } from "../charts/EquityDrawdownChart";
import { RotateCw, ExternalLink, Filter, Search, X, Sparkles, Cpu } from "lucide-react";

export const ExperimentsPage: React.FC = () => {
  const [experiments, setExperiments] = useState<Array<Record<string, unknown>>>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  // Filters & Search
  const [strategyFilter, setStrategyFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Detailed Modal / Inspector
  const [activeExperimentId, setActiveExperimentId] = useState<string | null>(null);
  const [activeDetail, setActiveDetail] = useState<ExperimentResult | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [rerunning, setRerunning] = useState(false);

  const fetchList = async () => {
    setLoadingList(true);
    setListError(null);
    try {
      const data = await listExperiments(200);
      setExperiments(data);
    } catch (err) {
      setListError((err as Error).message);
    } finally {
      setLoadingList(false);
    }
  };

  useEffect(() => {
    fetchList();
  }, []);

  const handleOpenExperiment = async (expId: string) => {
    setActiveExperimentId(expId);
    setLoadingDetail(true);
    setDetailError(null);
    try {
      const data = await getExperiment(expId);
      setActiveDetail(data);
    } catch (err) {
      setDetailError((err as Error).message);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleRerun = async () => {
    if (!activeExperimentId) return;
    setRerunning(true);
    try {
      const fresh = await rerunExperiment(activeExperimentId);
      setActiveDetail(fresh);
      fetchList();
    } catch (err) {
      setDetailError((err as Error).message);
    } finally {
      setRerunning(false);
    }
  };

  // Distinct strategy names for dropdown
  const uniqueStrategies = useMemo(() => {
    const s = new Set<string>();
    experiments.forEach((e) => {
      const name = String(e.strategy_name || e.strategy || "");
      if (name) s.add(name);
    });
    return Array.from(s);
  }, [experiments]);

  // Filtered experiments
  const filtered = useMemo(() => {
    return experiments.filter((e) => {
      const id = String(e.experiment_id || "").toLowerCase();
      const strat = String(e.strategy_name || e.strategy || "");
      const ds = String(e.dataset_id || e.dataset || "").toLowerCase();

      if (strategyFilter !== "ALL" && strat !== strategyFilter) {
        return false;
      }
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        if (!id.includes(q) && !strat.toLowerCase().includes(q) && !ds.includes(q)) {
          return false;
        }
      }
      return true;
    });
  }, [experiments, strategyFilter, searchQuery]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: "1.25rem", fontWeight: 700, letterSpacing: "-0.01em" }}>
          Experiment Repository
        </h1>
        <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
          Persisted, reproducible algorithmic trading research artifacts with cryptographic hash verification
        </p>
      </div>

      {/* Filter and Search Bar */}
      <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", alignItems: "center", backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "0.75rem 1rem", borderRadius: "4px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flex: 1, minWidth: "220px" }}>
          <Search size={16} style={{ color: "var(--text-muted)" }} />
          <input
            type="text"
            placeholder="Search by ID, strategy, or symbol..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ width: "100%" }}
          />
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <Filter size={16} style={{ color: "var(--text-muted)" }} />
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Strategy:</span>
          <select value={strategyFilter} onChange={(e) => setStrategyFilter(e.target.value)}>
            <option value="ALL">All Strategies</option>
            {uniqueStrategies.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>

        <button onClick={fetchList} className="btn btn-secondary btn-sm">
          <RotateCw size={14} /> Refresh
        </button>
      </div>

      {/* Experiments Table */}
      {loadingList ? (
        <LoadingSpinner message="Retrieving experiments from database..." />
      ) : listError ? (
        <ErrorMessage message={listError} onRetry={fetchList} />
      ) : filtered.length === 0 ? (
        <EmptyState title="No Experiments Found" message="Try adjusting your filter or execute a new backtest." />
      ) : (
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Experiment ID</th>
                <th>Strategy</th>
                <th>Dataset</th>
                <th>Date</th>
                <th>Total Return</th>
                <th>Sharpe</th>
                <th>Max Drawdown</th>
                <th>Trades</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((e) => {
                const id = String(e.experiment_id || "");
                const strat = String(e.strategy_name || e.strategy || "Unknown");
                const ds = String(e.dataset_id || e.dataset || "AAPL");
                const dt = String(e.created_at || e.date || "").split("T")[0];
                const metrics = (e.metrics as Record<string, number>) || {};
                const ret = metrics.total_return_pct ?? Number(e.return_pct ?? 0);
                const sharpe = metrics.sharpe_ratio ?? Number(e.sharpe ?? 0);
                const dd = metrics.max_drawdown_pct ?? Number(e.drawdown ?? 0);
                const trades = metrics.total_trades ?? Number(e.trades ?? 0);
                const isPos = ret >= 0;

                return (
                  <tr key={id}>
                    <td className="mono" style={{ fontWeight: 600 }}>{id}</td>
                    <td>{strat}</td>
                    <td className="mono">{ds}</td>
                    <td className="mono" style={{ color: "var(--text-secondary)" }}>{dt || "-"}</td>
                    <td className="mono" style={{ color: isPos ? "var(--status-green)" : "var(--status-red)", fontWeight: 600 }}>
                      {isPos ? "+" : ""}{(ret * 100).toFixed(2)}%
                    </td>
                    <td className="mono">{sharpe ? sharpe.toFixed(2) : "0.00"}</td>
                    <td className="mono" style={{ color: "var(--status-red)" }}>-{(dd * 100).toFixed(2)}%</td>
                    <td className="mono">{trades}</td>
                    <td>
                      <StatusBadge status="STORED" variant="green" />
                    </td>
                    <td>
                      <button
                        onClick={() => handleOpenExperiment(id)}
                        className="btn btn-secondary btn-sm"
                      >
                        Inspect <ExternalLink size={12} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Detailed Experiment Modal / Inspector Drawer */}
      {activeExperimentId && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.75)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            zIndex: 1000,
            padding: "2rem",
          }}
          onClick={() => setActiveExperimentId(null)}
        >
          <div
            style={{
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border-strong)",
              borderRadius: "6px",
              width: "100%",
              maxWidth: "1000px",
              maxHeight: "90vh",
              overflowY: "auto",
              padding: "1.5rem",
              display: "flex",
              flexDirection: "column",
              gap: "1.25rem",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", borderBottom: "1px solid var(--border-subtle)", paddingBottom: "1rem" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <h2 style={{ fontSize: "1.2rem", fontWeight: 700 }}>
                    Experiment Inspector: {activeExperimentId}
                  </h2>
                  <StatusBadge status="VALIDATED" variant="green" />
                </div>
                {activeDetail && (
                  <div className="mono" style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
                    Config SHA-256: <strong>{activeDetail.configuration_hash}</strong>
                  </div>
                )}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <button onClick={handleRerun} disabled={rerunning} className="btn btn-primary btn-sm">
                  <RotateCw size={14} className={rerunning ? "animate-spin" : ""} /> Rerun Experiment
                </button>
                <button onClick={() => setActiveExperimentId(null)} className="btn btn-secondary btn-sm">
                  <X size={16} />
                </button>
              </div>
            </div>

            {loadingDetail ? (
              <LoadingSpinner message="Loading full experiment artifacts..." />
            ) : detailError ? (
              <ErrorMessage message={detailError} />
            ) : activeDetail ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                {/* Performance Metrics */}
                <div>
                  <h3 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.5rem" }}>
                    PERFORMANCE METRICS
                  </h3>
                  <MetricsGrid metrics={activeDetail.metrics} />
                </div>

                {/* AI / ML Metrics if available */}
                {activeDetail.ai_decision_stats && (
                  <div style={{ backgroundColor: "var(--bg-app)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
                    <div style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--accent-blue)", marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                      <Sparkles size={16} /> JEV AI ADVISORY STATISTICS
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "0.5rem", fontSize: "0.75rem" }} className="mono">
                      <div>Model: <strong>{activeDetail.ai_decision_stats.model}</strong></div>
                      <div>Total Decisions: <strong>{activeDetail.ai_decision_stats.total_decisions}</strong></div>
                      <div>BUY Count: <strong style={{ color: "var(--status-green)" }}>{activeDetail.ai_decision_stats.buy_count}</strong></div>
                      <div>SELL Count: <strong style={{ color: "var(--status-red)" }}>{activeDetail.ai_decision_stats.sell_count}</strong></div>
                      <div>HOLD Count: <strong>{activeDetail.ai_decision_stats.hold_count}</strong></div>
                      <div>Avg Conf: <strong>{(activeDetail.ai_decision_stats.avg_confidence * 100).toFixed(1)}%</strong></div>
                      <div>Cache Hits: <strong>{activeDetail.ai_decision_stats.cache_hits}</strong></div>
                      <div>Fallbacks: <strong>{activeDetail.ai_decision_stats.fallbacks}</strong></div>
                    </div>
                  </div>
                )}

                {/* Classification Metrics if ML */}
                {activeDetail.classification_metrics && (
                  <div style={{ backgroundColor: "var(--bg-app)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
                    <div style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--status-purple)", marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
                      <Cpu size={16} /> SUPERVISED ML CLASSIFICATION METRICS
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "0.5rem", fontSize: "0.75rem" }} className="mono">
                      <div>Accuracy: <strong>{(activeDetail.classification_metrics.accuracy * 100).toFixed(2)}%</strong></div>
                      <div>Precision: <strong>{(activeDetail.classification_metrics.precision * 100).toFixed(2)}%</strong></div>
                      <div>Recall: <strong>{(activeDetail.classification_metrics.recall * 100).toFixed(2)}%</strong></div>
                      <div>F1 Score: <strong>{activeDetail.classification_metrics.f1.toFixed(3)}</strong></div>
                      <div>ROC-AUC: <strong>{activeDetail.classification_metrics.roc_auc.toFixed(3)}</strong></div>
                      <div>Brier Score: <strong>{activeDetail.classification_metrics.brier_score.toFixed(4)}</strong></div>
                    </div>
                  </div>
                )}

                {/* Equity & Drawdown Curves */}
                <div>
                  <h3 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.5rem" }}>
                    EQUITY &amp; DRAWDOWN CURVES
                  </h3>
                  <EquityDrawdownChart
                    equityCurve={activeDetail.equity_curve}
                    drawdownCurve={activeDetail.drawdown_curve}
                    initialCapital={Number(activeDetail.execution_statistics?.initial_capital) || 100000}
                    height={260}
                  />
                </div>

                {/* Trade Execution Log */}
                <div>
                  <h3 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.5rem" }}>
                    TRADE LOG ({activeDetail.trade_records.length} TRADES)
                  </h3>
                  <TradeHistoryTable trades={activeDetail.trade_records} />
                </div>

                {/* Raw Config JSON */}
                <div>
                  <h3 style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.5rem" }}>
                    EXPERIMENT CONFIGURATION PAYLOAD
                  </h3>
                  <pre
                    className="mono"
                    style={{
                      backgroundColor: "var(--bg-app)",
                      padding: "1rem",
                      borderRadius: "4px",
                      fontSize: "0.75rem",
                      maxHeight: "180px",
                      overflowY: "auto",
                      border: "1px solid var(--border-subtle)",
                    }}
                  >
                    {JSON.stringify(activeDetail.config, null, 2)}
                  </pre>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
};
