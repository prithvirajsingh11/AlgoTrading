import React, { useState, useEffect } from "react";
import { getPortfolioSummary, listPositions } from "../services/portfolio";
import { PortfolioSummary, Position } from "../types";
import { LoadingSpinner, ErrorMessage, StatusBadge, EmptyState } from "../components/Common";
import { RefreshCw } from "lucide-react";

export const PortfolioPage: React.FC = () => {
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPortfolio = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sum, pos] = await Promise.all([getPortfolioSummary(), listPositions()]);
      setSummary(sum);
      setPositions(pos);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPortfolio();
  }, []);

  if (loading) return <LoadingSpinner message="Fetching portfolio state and open positions..." />;
  if (error) return <ErrorMessage message={error} onRetry={fetchPortfolio} />;

  const initialCapital = summary?.initial_capital ?? 100000;
  const currentCash = summary?.current_cash ?? initialCapital;
  const totalEquity = summary?.total_equity ?? currentCash;
  const realizedPnl = summary?.realized_pnl ?? 0;
  const unrealizedPnl = summary?.unrealized_pnl ?? 0;
  const exposurePct = summary?.current_exposure ?? 0;

  // Identify pair positions by pair_id if any
  const pairGroups = positions.reduce((acc, p) => {
    if (p.pair_id) {
      if (!acc[p.pair_id]) acc[p.pair_id] = [];
      acc[p.pair_id].push(p);
    }
    return acc;
  }, {} as Record<string, Position[]>);

  const singlePositions = positions.filter((p) => !p.pair_id);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 style={{ fontSize: "1.25rem", fontWeight: 700, letterSpacing: "-0.01em" }}>
            Portfolio &amp; Position Manager
          </h1>
          <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
            Portfolio-ready position tracking, cash accounting, long/short exposure, and multi-asset pairs breakdown
          </p>
        </div>
        <button onClick={fetchPortfolio} className="btn btn-secondary btn-sm">
          <RefreshCw size={14} /> Refresh Portfolio
        </button>
      </div>

      {/* Capital Accounting Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "1rem" }}>
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Total Equity</div>
          <div className="mono" style={{ fontSize: "1.35rem", fontWeight: 700, margin: "0.25rem 0" }}>
            ${totalEquity.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Currency: {summary?.currency || "USD"}</div>
        </div>

        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Available Cash</div>
          <div className="mono" style={{ fontSize: "1.35rem", fontWeight: 700, margin: "0.25rem 0" }}>
            ${currentCash.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Initial: ${initialCapital.toLocaleString()}</div>
        </div>

        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Realized P&amp;L</div>
          <div className="mono" style={{ fontSize: "1.35rem", fontWeight: 700, margin: "0.25rem 0", color: realizedPnl >= 0 ? "var(--status-green)" : "var(--status-red)" }}>
            {realizedPnl >= 0 ? "+" : ""}${realizedPnl.toFixed(2)}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Closed Trades</div>
        </div>

        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Unrealized P&amp;L</div>
          <div className="mono" style={{ fontSize: "1.35rem", fontWeight: 700, margin: "0.25rem 0", color: unrealizedPnl >= 0 ? "var(--status-green)" : "var(--status-red)" }}>
            {unrealizedPnl >= 0 ? "+" : ""}${unrealizedPnl.toFixed(2)}
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Floating P&amp;L</div>
        </div>

        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
          <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Market Exposure</div>
          <div className="mono" style={{ fontSize: "1.35rem", fontWeight: 700, margin: "0.25rem 0" }}>
            {(exposurePct * 100).toFixed(1)}%
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Open Positions: {positions.length}</div>
        </div>
      </div>

      {/* Pairs Positions Breakdown */}
      {Object.keys(pairGroups).length > 0 && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem" }}>
          <h2 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "0.75rem", color: "var(--accent-blue)" }}>
            Synchronized Pairs Trading Positions
          </h2>
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {Object.entries(pairGroups).map(([pairId, legs]) => {
              const combinedPnl = legs.reduce((sum, leg) => sum + leg.unrealized_pnl, 0);
              const isGreen = combinedPnl >= 0;
              return (
                <div key={pairId} style={{ backgroundColor: "var(--bg-app)", border: "1px solid var(--border-strong)", borderRadius: "4px", padding: "1rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem", borderBottom: "1px solid var(--border-subtle)", paddingBottom: "0.5rem" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>PAIR: {pairId}</span>
                      <StatusBadge status="SYNCHRONIZED TWO-LEG" variant="blue" />
                    </div>
                    <div className="mono" style={{ fontSize: "0.9rem", fontWeight: 700, color: isGreen ? "var(--status-green)" : "var(--status-red)" }}>
                      Combined P&amp;L: {isGreen ? "+" : ""}${combinedPnl.toFixed(2)}
                    </div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                    {legs.map((leg) => {
                      const isLong = leg.quantity > 0;
                      return (
                        <div key={leg.symbol} style={{ backgroundColor: "var(--bg-surface)", padding: "0.75rem", borderRadius: "3px", border: "1px solid var(--border-subtle)" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.35rem" }}>
                            <span className="mono" style={{ fontWeight: 700 }}>{leg.symbol}</span>
                            <StatusBadge status={isLong ? "LONG" : "SHORT"} variant={isLong ? "blue" : "red"} />
                          </div>
                          <div className="mono" style={{ fontSize: "0.75rem", display: "flex", flexDirection: "column", gap: "0.2rem" }}>
                            <div>Quantity: <strong>{isLong ? `+${leg.quantity}` : leg.quantity}</strong></div>
                            <div>Entry Price: <strong>${leg.avg_entry_price.toFixed(2)}</strong></div>
                            <div>Current Price: <strong>${leg.current_price.toFixed(2)}</strong></div>
                            <div>P&amp;L: <strong style={{ color: leg.unrealized_pnl >= 0 ? "var(--status-green)" : "var(--status-red)" }}>{leg.unrealized_pnl >= 0 ? "+" : ""}${leg.unrealized_pnl.toFixed(2)}</strong></div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Standard Open Positions Table */}
      <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem" }}>
        <h2 style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: "0.75rem" }}>
          Active Portfolio Positions ({singlePositions.length})
        </h2>

        {singlePositions.length === 0 ? (
          <EmptyState
            title="Zero Active Market Exposure"
            message="All simulated positions are closed. Current portfolio is 100% in cash."
          />
        ) : (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Leg Type</th>
                  <th>Quantity</th>
                  <th>Avg Entry Price</th>
                  <th>Current Price</th>
                  <th>Market Value</th>
                  <th>Unrealized P&amp;L</th>
                  <th>Return (%)</th>
                </tr>
              </thead>
              <tbody>
                {singlePositions.map((pos) => {
                  const isProfitable = pos.unrealized_pnl >= 0;
                  return (
                    <tr key={pos.symbol}>
                      <td className="mono" style={{ fontWeight: 700 }}>{pos.symbol}</td>
                      <td>
                        <StatusBadge
                          status={pos.leg_type || (pos.quantity >= 0 ? "LONG" : "SHORT")}
                          variant={pos.quantity >= 0 ? "blue" : "red"}
                        />
                      </td>
                      <td className="mono">{pos.quantity}</td>
                      <td className="mono">${pos.avg_entry_price.toFixed(2)}</td>
                      <td className="mono">${pos.current_price.toFixed(2)}</td>
                      <td className="mono">${pos.market_value.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                      <td className="mono" style={{ color: isProfitable ? "var(--status-green)" : "var(--status-red)", fontWeight: 700 }}>
                        {isProfitable ? "+" : ""}${pos.unrealized_pnl.toFixed(2)}
                      </td>
                      <td className="mono" style={{ color: isProfitable ? "var(--status-green)" : "var(--status-red)" }}>
                        {isProfitable ? "+" : ""}{(pos.unrealized_pnl_pct * 100).toFixed(2)}%
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
