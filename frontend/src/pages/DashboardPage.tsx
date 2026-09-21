import React, { useState, useEffect } from "react";
import { getPortfolioSummary } from "../services/portfolio";
import { listExperiments, getExperiment } from "../services/experiments";
import { listStrategies } from "../services/strategies";
import { PortfolioSummary, StrategyMetadata, ExperimentResult } from "../types";
import { LoadingSpinner, ErrorMessage, StatusBadge, EmptyState } from "../components/Common";
import { EquityDrawdownChart } from "../charts/EquityDrawdownChart";
import { ArrowUpRight, TrendingUp } from "lucide-react";

interface DashboardPageProps {
  onNavigate: (route: string) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onNavigate }) => {
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [strategies, setStrategies] = useState<StrategyMetadata[]>([]);
  const [recentExperiments, setRecentExperiments] = useState<Array<Record<string, unknown>>>([]);
  const [latestResult, setLatestResult] = useState<ExperimentResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [pRes, sRes, eRes] = await Promise.all([
        getPortfolioSummary(),
        listStrategies(),
        listExperiments(5),
      ]);
      setPortfolio(pRes);
      setStrategies(sRes);
      setRecentExperiments(eRes);

      if (eRes.length > 0 && eRes[0].experiment_id) {
        try {
          const detail = await getExperiment(String(eRes[0].experiment_id));
          setLatestResult(detail);
        } catch {
          // ignore if experiment detail not loadable
        }
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) return <LoadingSpinner message="Loading dashboard metrics..." />;
  if (error) return <ErrorMessage message={error} onRetry={fetchData} />;

  const initialCapital = portfolio?.initial_capital ?? 100000;
  const currentCash = portfolio?.current_cash ?? initialCapital;
  const totalEquity = portfolio?.total_equity ?? currentCash;
  const unrealizedPnl = portfolio?.unrealized_pnl ?? 0.0;
  const realizedPnl = portfolio?.realized_pnl ?? 0.0;
  const currentExposure = portfolio?.current_exposure ?? 0.0;
  const drawdown = portfolio?.drawdown_pct ?? 0.0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Page Title */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 style={{ fontSize: "1.25rem", fontWeight: 700, letterSpacing: "-0.01em" }}>
            Quantitative Research Dashboard
          </h1>
          <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
            Institutional backtest monitoring, portfolio state, and active strategy registry
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          <button onClick={() => onNavigate("backtests")} className="btn btn-primary btn-sm">
            <TrendingUp size={14} /> Run New Backtest
          </button>
        </div>
      </div>

      {/* Section A: Portfolio Summary */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: "1rem" }}>
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
            Current Equity
          </div>
          <div className="mono" style={{ fontSize: "1.35rem", fontWeight: 700, margin: "0.25rem 0" }}>
            ${totalEquity.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
            Initial: ${initialCapital.toLocaleString()}
          </div>
        </div>

        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
            Available Cash
          </div>
          <div className="mono" style={{ fontSize: "1.35rem", fontWeight: 700, margin: "0.25rem 0" }}>
            ${currentCash.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
            Reserve Capital
          </div>
        </div>

        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
            Realized P&amp;L
          </div>
          <div className="mono" style={{ fontSize: "1.35rem", fontWeight: 700, margin: "0.25rem 0", color: realizedPnl >= 0 ? "var(--status-green)" : "var(--status-red)" }}>
            {realizedPnl >= 0 ? "+" : ""}${realizedPnl.toFixed(2)}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
            Closed Positions
          </div>
        </div>

        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
            Unrealized P&amp;L
          </div>
          <div className="mono" style={{ fontSize: "1.35rem", fontWeight: 700, margin: "0.25rem 0", color: unrealizedPnl >= 0 ? "var(--status-green)" : "var(--status-red)" }}>
            {unrealizedPnl >= 0 ? "+" : ""}${unrealizedPnl.toFixed(2)}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
            Mark-to-Market
          </div>
        </div>

        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
            Market Exposure
          </div>
          <div className="mono" style={{ fontSize: "1.35rem", fontWeight: 700, margin: "0.25rem 0" }}>
            {(currentExposure * 100).toFixed(1)}%
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
            Limit: 50.0% Max
          </div>
        </div>

        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: 600 }}>
            Current Drawdown
          </div>
          <div className="mono" style={{ fontSize: "1.35rem", fontWeight: 700, margin: "0.25rem 0", color: drawdown > 0.15 ? "var(--status-red)" : "var(--text-primary)" }}>
            {(drawdown * 100).toFixed(2)}%
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
            Circuit Breaker: 30%
          </div>
        </div>
      </div>

      {/* Section B: Latest Performance Curves */}
      {latestResult && latestResult.equity_curve && latestResult.equity_curve.length > 0 ? (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
            <h2 style={{ fontSize: "0.95rem", fontWeight: 600 }}>
              Recent Research Performance: {latestResult.strategy_info?.name} ({latestResult.experiment_id})
            </h2>
            <button onClick={() => onNavigate("experiments")} className="btn btn-secondary btn-sm">
              View All Experiments <ArrowUpRight size={12} />
            </button>
          </div>
          <EquityDrawdownChart
            equityCurve={latestResult.equity_curve}
            drawdownCurve={latestResult.drawdown_curve}
            initialCapital={Number(latestResult.execution_statistics?.initial_capital) || 100000}
            height={280}
          />
        </div>
      ) : (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1.5rem", borderRadius: "4px", textAlign: "center" }}>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", marginBottom: "0.75rem" }}>
            No recent experiment curves available. Run your first reproducible backtest in the Backtest Lab.
          </p>
          <button onClick={() => onNavigate("backtests")} className="btn btn-primary btn-sm">
            Launch Backtest
          </button>
        </div>
      )}

      {/* Section C: Strategy Overview */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
          <h2 style={{ fontSize: "0.95rem", fontWeight: 600 }}>
            Configured Strategy Registry
          </h2>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
            Zero frontend ranking score — Authoritative backend catalog
          </span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "1rem" }}>
          {strategies.map((strat) => (
            <div
              key={strat.id}
              style={{
                backgroundColor: "var(--bg-surface)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "4px",
                padding: "1rem",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
              }}
            >
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.5rem" }}>
                  <div>
                    <h3 style={{ fontSize: "0.875rem", fontWeight: 600 }}>{strat.name}</h3>
                    <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>{strat.category} · {strat.id}</span>
                  </div>
                  <StatusBadge status={strat.status} />
                </div>
                <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginBottom: "0.75rem" }}>
                  {strat.description}
                </p>
              </div>

              <div>
                <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: "0.25rem", textTransform: "uppercase" }}>
                  Configurable Parameters ({strat.parameters.length}):
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
                  {strat.parameters.map((p) => (
                    <span
                      key={p.name}
                      className="mono"
                      style={{
                        fontSize: "0.7rem",
                        backgroundColor: "var(--bg-surface-elevated)",
                        border: "1px solid var(--border-strong)",
                        padding: "0.15rem 0.4rem",
                        borderRadius: "3px",
                      }}
                    >
                      {p.name}: {String(p.default)}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Section D: Recent Experiments */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
          <h2 style={{ fontSize: "0.95rem", fontWeight: 600 }}>
            Recent Experiments
          </h2>
          <button onClick={() => onNavigate("experiments")} className="btn btn-secondary btn-sm">
            Browse All ({recentExperiments.length})
          </button>
        </div>

        {recentExperiments.length === 0 ? (
          <EmptyState title="No Experiments Yet" message="Execute your first experiment to view metrics here." />
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Experiment ID</th>
                  <th>Strategy</th>
                  <th>Dataset</th>
                  <th>Date</th>
                  <th>Return</th>
                  <th>Sharpe</th>
                  <th>Max DD</th>
                  <th>Trades</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {recentExperiments.map((exp, idx) => {
                  const id = String(exp.experiment_id || `exp_${idx}`);
                  const strat = String(exp.strategy_name || exp.strategy || "Unknown");
                  const ds = String(exp.dataset_id || exp.dataset || "AAPL");
                  const dt = String(exp.created_at || exp.date || "").split("T")[0];
                  const metrics = (exp.metrics as Record<string, number>) || {};
                  const ret = metrics.total_return_pct ?? Number(exp.return_pct ?? 0);
                  const sharpe = metrics.sharpe_ratio ?? Number(exp.sharpe ?? 0);
                  const dd = metrics.max_drawdown_pct ?? Number(exp.drawdown ?? 0);
                  const trades = metrics.total_trades ?? Number(exp.trades ?? 0);
                  const isPositive = ret >= 0;

                  return (
                    <tr key={id}>
                      <td className="mono" style={{ fontWeight: 600 }}>{id}</td>
                      <td>{strat}</td>
                      <td className="mono">{ds}</td>
                      <td className="mono" style={{ color: "var(--text-secondary)" }}>{dt || "-"}</td>
                      <td className="mono" style={{ color: isPositive ? "var(--status-green)" : "var(--status-red)", fontWeight: 600 }}>
                        {isPositive ? "+" : ""}{(ret * 100).toFixed(2)}%
                      </td>
                      <td className="mono">{sharpe ? sharpe.toFixed(2) : "0.00"}</td>
                      <td className="mono" style={{ color: "var(--status-red)" }}>-{(dd * 100).toFixed(2)}%</td>
                      <td className="mono">{trades}</td>
                      <td>
                        <StatusBadge status="COMPLETED" variant="green" />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
