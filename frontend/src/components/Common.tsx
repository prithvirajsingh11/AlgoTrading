import React from "react";
import { Loader2, AlertCircle, Inbox } from "lucide-react";
import { BacktestMetrics, TradeRecord } from "../types";

export const LoadingSpinner: React.FC<{ message?: string }> = ({
  message = "Loading data from backend...",
}) => (
  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "3rem 1rem", color: "var(--text-secondary)" }}>
    <Loader2 className="animate-spin" size={32} style={{ color: "var(--accent-blue)", marginBottom: "1rem", animation: "spin 1s linear infinite" }} />
    <style>{`@keyframes spin { 100% { transform: rotate(360deg); } }`}</style>
    <div style={{ fontSize: "0.875rem", fontWeight: 500 }}>{message}</div>
  </div>
);

export const ErrorMessage: React.FC<{ message: string; onRetry?: () => void }> = ({
  message,
  onRetry,
}) => (
  <div style={{ display: "flex", alignItems: "flex-start", gap: "0.75rem", padding: "1rem", backgroundColor: "var(--status-red-subtle)", border: "1px solid rgba(239, 68, 68, 0.3)", borderRadius: "4px", color: "var(--status-red)", margin: "1rem 0" }}>
    <AlertCircle size={20} style={{ flexShrink: 0, marginTop: "2px" }} />
    <div style={{ flex: 1 }}>
      <div style={{ fontWeight: 600, fontSize: "0.875rem", marginBottom: "0.25rem" }}>System Error</div>
      <div style={{ fontSize: "0.8125rem", wordBreak: "break-word" }}>{message}</div>
      {onRetry && (
        <button onClick={onRetry} className="btn btn-secondary btn-sm" style={{ marginTop: "0.75rem" }}>
          Retry Request
        </button>
      )}
    </div>
  </div>
);

export const EmptyState: React.FC<{ title: string; message: string }> = ({
  title,
  message,
}) => (
  <div style={{ textAlign: "center", padding: "3rem 1.5rem", border: "1px dashed var(--border-strong)", borderRadius: "6px", color: "var(--text-muted)" }}>
    <Inbox size={40} style={{ margin: "0 auto 0.75rem", opacity: 0.5 }} />
    <h3 style={{ fontSize: "1rem", color: "var(--text-secondary)", marginBottom: "0.25rem" }}>{title}</h3>
    <p style={{ fontSize: "0.8125rem" }}>{message}</p>
  </div>
);

export const StatusBadge: React.FC<{
  status: string;
  variant?: "green" | "red" | "amber" | "blue" | "gray";
}> = ({ status, variant }) => {
  let v = variant;
  if (!v) {
    const s = status.toUpperCase();
    if (s.includes("ACTIVE") || s.includes("VALID") || s.includes("READY") || s.includes("BUY") || s.includes("PROFIT")) {
      v = "green";
    } else if (s.includes("INVALID") || s.includes("ERROR") || s.includes("SELL") || s.includes("LOSS") || s.includes("DISABLED")) {
      v = "red";
    } else if (s.includes("WARNING") || s.includes("STANDBY") || s.includes("HOLD") || s.includes("UNCONFIGURED")) {
      v = "amber";
    } else {
      v = "gray";
    }
  }

  return <span className={`badge badge-${v}`}>{status}</span>;
};

export const MetricsGrid: React.FC<{ metrics: BacktestMetrics }> = ({ metrics }) => {
  const isPositive = (metrics.total_return_pct ?? 0) >= 0;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "1rem", margin: "1rem 0" }}>
      <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
        <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.35rem" }}>
          Total Return
        </div>
        <div className="mono" style={{ fontSize: "1.25rem", fontWeight: 700, color: isPositive ? "var(--status-green)" : "var(--status-red)" }}>
          {isPositive ? "+" : ""}{(metrics.total_return_pct * 100).toFixed(2)}%
        </div>
      </div>

      <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
        <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.35rem" }}>
          CAGR
        </div>
        <div className="mono" style={{ fontSize: "1.25rem", fontWeight: 700 }}>
          {(metrics.cagr * 100).toFixed(2)}%
        </div>
      </div>

      <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
        <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.35rem" }}>
          Sharpe Ratio
        </div>
        <div className="mono" style={{ fontSize: "1.25rem", fontWeight: 700 }}>
          {metrics.sharpe_ratio != null ? metrics.sharpe_ratio.toFixed(2) : "N/A"}
        </div>
      </div>

      <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
        <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.35rem" }}>
          Sortino Ratio
        </div>
        <div className="mono" style={{ fontSize: "1.25rem", fontWeight: 700 }}>
          {metrics.sortino_ratio != null ? metrics.sortino_ratio.toFixed(2) : "N/A"}
        </div>
      </div>

      <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
        <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.35rem" }}>
          Max Drawdown
        </div>
        <div className="mono" style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--status-red)" }}>
          -{(metrics.max_drawdown_pct * 100).toFixed(2)}%
        </div>
      </div>

      <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
        <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.35rem" }}>
          Win Rate
        </div>
        <div className="mono" style={{ fontSize: "1.25rem", fontWeight: 700 }}>
          {(metrics.win_rate * 100).toFixed(1)}%
        </div>
      </div>

      <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
        <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.35rem" }}>
          Profit Factor
        </div>
        <div className="mono" style={{ fontSize: "1.25rem", fontWeight: 700 }}>
          {metrics.profit_factor != null ? metrics.profit_factor.toFixed(2) : "N/A"}
        </div>
      </div>

      <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
        <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "0.35rem" }}>
          Total Trades
        </div>
        <div className="mono" style={{ fontSize: "1.25rem", fontWeight: 700 }}>
          {metrics.total_trades}
        </div>
      </div>
    </div>
  );
};

export const TradeHistoryTable: React.FC<{ trades: TradeRecord[] }> = ({ trades }) => {
  if (!trades || trades.length === 0) {
    return <EmptyState title="No Trades" message="No trades were executed during this backtest run." />;
  }

  return (
    <div className="table-container">
      <table>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Direction</th>
            <th>Entry Time</th>
            <th>Exit Time</th>
            <th>Size</th>
            <th>Entry Price</th>
            <th>Exit Price</th>
            <th>P&amp;L ($)</th>
            <th>P&amp;L (%)</th>
            <th>Exit Reason</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t, idx) => {
            const isProfitable = t.pnl >= 0;
            return (
              <tr key={idx}>
                <td className="mono" style={{ fontWeight: 600 }}>{t.symbol}</td>
                <td>
                  <StatusBadge status={t.direction} variant={t.direction === "LONG" ? "blue" : "amber"} />
                </td>
                <td className="mono" style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                  {t.entry_time ? t.entry_time.split("T")[0] : "-"}
                </td>
                <td className="mono" style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                  {t.exit_time ? t.exit_time.split("T")[0] : "-"}
                </td>
                <td className="mono">{t.size}</td>
                <td className="mono">${t.entry_price.toFixed(2)}</td>
                <td className="mono">${t.exit_price.toFixed(2)}</td>
                <td className="mono" style={{ color: isProfitable ? "var(--status-green)" : "var(--status-red)", fontWeight: 600 }}>
                  {isProfitable ? "+" : ""}${t.pnl.toFixed(2)}
                </td>
                <td className="mono" style={{ color: isProfitable ? "var(--status-green)" : "var(--status-red)" }}>
                  {isProfitable ? "+" : ""}{(t.pnl_pct * 100).toFixed(2)}%
                </td>
                <td style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{t.exit_reason}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
