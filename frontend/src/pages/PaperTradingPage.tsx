import React, { useState, useEffect } from "react";
import { getPaperStatus } from "../services/portfolio";
import { PaperTradingStatus } from "../types";
import { LoadingSpinner, ErrorMessage, StatusBadge, EmptyState } from "../components/Common";
import { ShieldAlert, RefreshCw } from "lucide-react";

export const PaperTradingPage: React.FC = () => {
  const [status, setStatus] = useState<PaperTradingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPaperStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      const s = await getPaperStatus();
      setStatus(s);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPaperStatus();
  }, []);

  if (loading) return <LoadingSpinner message="Checking paper trading engine daemon status..." />;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: "1.25rem", fontWeight: 700, letterSpacing: "-0.01em" }}>
          Live Paper Trading Console
        </h1>
        <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
          Simulated order execution daemon and virtual account management
        </p>
      </div>

      {/* Prominent Safety & Simulation Disclosure */}
      <div
        style={{
          backgroundColor: "rgba(239, 68, 68, 0.08)",
          border: "1px solid rgba(239, 68, 68, 0.3)",
          borderRadius: "6px",
          padding: "1rem 1.25rem",
          display: "flex",
          alignItems: "center",
          gap: "1rem",
        }}
      >
        <ShieldAlert size={28} style={{ color: "var(--status-red)", flexShrink: 0 }} />
        <div>
          <div style={{ fontWeight: 800, fontSize: "0.95rem", color: "var(--status-red)", letterSpacing: "0.04em" }}>
            PAPER TRADING ENVIRONMENT — NO REAL MONEY
          </div>
          <div style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", marginTop: "0.2rem" }}>
            All orders, capital balances, and executions are strictly simulated in-memory. Brokerage API connections are disabled by architecture invariants.
          </div>
        </div>
      </div>

      {error && <ErrorMessage message={error} onRetry={fetchPaperStatus} />}

      {/* Engine Status Card */}
      <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <h2 style={{ fontSize: "1rem", fontWeight: 700 }}>Execution Engine Daemon</h2>
            <StatusBadge status={status?.is_active ? "RUNNING" : "STANDBY"} variant={status?.is_active ? "green" : "amber"} />
          </div>
          <button onClick={fetchPaperStatus} className="btn btn-secondary btn-sm">
            <RefreshCw size={14} /> Refresh Status
          </button>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "1rem", fontSize: "0.8125rem" }} className="mono">
          <div style={{ backgroundColor: "var(--bg-app)", padding: "0.75rem", borderRadius: "4px" }}>
            <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>MODE</div>
            <div style={{ fontWeight: 700, marginTop: "0.2rem" }}>{status?.mode || "SIMULATION_ONLY"}</div>
          </div>
          <div style={{ backgroundColor: "var(--bg-app)", padding: "0.75rem", borderRadius: "4px" }}>
            <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>VIRTUAL CASH</div>
            <div style={{ fontWeight: 700, marginTop: "0.2rem" }}>$100,000.00 USD</div>
          </div>
          <div style={{ backgroundColor: "var(--bg-app)", padding: "0.75rem", borderRadius: "4px" }}>
            <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>HEARTBEAT</div>
            <div style={{ fontWeight: 700, marginTop: "0.2rem" }}>STANDBY READY</div>
          </div>
          <div style={{ backgroundColor: "var(--bg-app)", padding: "0.75rem", borderRadius: "4px" }}>
            <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>SYSTEM MESSAGE</div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "0.2rem" }}>{status?.message}</div>
          </div>
        </div>
      </div>

      {/* Simulated Orders & Executions Table */}
      <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem" }}>
        <h3 style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: "0.75rem" }}>
          Active Orders &amp; Executions Queue
        </h3>
        <EmptyState
          title="No Active Paper Orders"
          message="The simulated order matching engine is standing by. Live background paper feed connects in subsequent live trading phase."
        />
      </div>
    </div>
  );
};
