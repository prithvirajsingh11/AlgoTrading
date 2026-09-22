import React, { useState } from "react";
import { getApiBaseUrl, setApiBaseUrl } from "../services/api";
import { Save, CheckCircle2, RefreshCw, Server, Sliders, Shield } from "lucide-react";

export const SettingsPage: React.FC = () => {
  const [apiUrl, setApiUrl] = useState<string>(getApiBaseUrl());
  const [testStatus, setTestStatus] = useState<"idle" | "testing" | "success" | "failed">("idle");
  const [savedSuccess, setSavedSuccess] = useState(false);

  // Defaults
  const [defaultDataset, setDefaultDataset] = useState("AAPL");
  const [defaultStrategy, setDefaultStrategy] = useState("MovingAverageCross");
  const [defaultCapital, setDefaultCapital] = useState(100000);
  const [defaultSlippage, setDefaultSlippage] = useState(5.0);

  const handleTestConnection = async () => {
    setTestStatus("testing");
    try {
      const cleanUrl = apiUrl.replace(/\/+$/, "");
      const res = await fetch(`${cleanUrl}/health`);
      if (res.ok) {
        setTestStatus("success");
      } else {
        setTestStatus("failed");
      }
    } catch {
      setTestStatus("failed");
    }
  };

  const handleSaveSettings = (e: React.FormEvent) => {
    e.preventDefault();
    setApiBaseUrl(apiUrl);
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 3000);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem", maxWidth: "800px" }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: "1.25rem", fontWeight: 700, letterSpacing: "-0.01em" }}>
          Platform Settings &amp; Configuration
        </h1>
        <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
          Manage API endpoint routing, simulation defaults, and financial charting preferences
        </p>
      </div>

      {savedSuccess && (
        <div style={{ padding: "0.75rem 1rem", backgroundColor: "var(--status-green-subtle)", border: "1px solid rgba(16, 185, 129, 0.3)", borderRadius: "4px", color: "var(--status-green)", fontSize: "0.8125rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <CheckCircle2 size={16} /> Configuration saved to browser storage.
        </div>
      )}

      <form onSubmit={handleSaveSettings} style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        {/* Backend API Connection */}
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem" }}>
          <div style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: "0.75rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <Server size={16} style={{ color: "var(--accent-blue)" }} /> FastAPI Backend Service URL
          </div>
          <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginBottom: "1rem" }}>
            The frontend connects to this base URL for market feeds, backtest executions, and ML training.
          </p>

          <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", marginBottom: "0.75rem" }}>
            <input
              type="text"
              value={apiUrl}
              onChange={(e) => {
                setApiUrl(e.target.value);
                setTestStatus("idle");
              }}
              style={{ flex: 1 }}
              placeholder="http://localhost:8000"
            />
            <button type="button" onClick={handleTestConnection} disabled={testStatus === "testing"} className="btn btn-secondary btn-sm">
              {testStatus === "testing" ? <RefreshCw size={14} className="animate-spin" /> : "Test Connection"}
            </button>
          </div>

          <div style={{ fontSize: "0.75rem" }}>
            {testStatus === "success" && <span style={{ color: "var(--status-green)" }}>✓ Connection successful: FastAPI backend is healthy.</span>}
            {testStatus === "failed" && <span style={{ color: "var(--status-red)" }}>✗ Connection failed: Unable to reach /health endpoint.</span>}
          </div>
        </div>

        {/* Backtest & Simulation Defaults */}
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem" }}>
          <div style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: "0.75rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <Sliders size={16} style={{ color: "var(--accent-blue)" }} /> Research &amp; Backtest Defaults
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
            <div>
              <label style={{ display: "block", fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: "0.25rem", textTransform: "uppercase" }}>Default Asset</label>
              <input type="text" value={defaultDataset} onChange={(e) => setDefaultDataset(e.target.value)} style={{ width: "100%" }} />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: "0.25rem", textTransform: "uppercase" }}>Default Strategy</label>
              <input type="text" value={defaultStrategy} onChange={(e) => setDefaultStrategy(e.target.value)} style={{ width: "100%" }} />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: "0.25rem", textTransform: "uppercase" }}>Default Capital ($)</label>
              <input type="number" value={defaultCapital} onChange={(e) => setDefaultCapital(Number(e.target.value))} style={{ width: "100%" }} />
            </div>

            <div>
              <label style={{ display: "block", fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: "0.25rem", textTransform: "uppercase" }}>Default Slippage (bps)</label>
              <input type="number" value={defaultSlippage} onChange={(e) => setDefaultSlippage(Number(e.target.value))} style={{ width: "100%" }} />
            </div>
          </div>
        </div>

        {/* Security & Secrets Policy */}
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem" }}>
          <div style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <Shield size={16} style={{ color: "var(--status-green)" }} /> Secret Isolation Policy
          </div>
          <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
            In compliance with algorithmic research security guidelines, server environment variables (such as <code>JEV_API_KEY</code>) are managed exclusively through <code>.env</code> on the backend and are never displayed or stored in browser memory.
          </p>
        </div>

        {/* About & System Invariants */}
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem" }}>
          <div style={{ fontSize: "0.875rem", fontWeight: 600, marginBottom: "0.5rem", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <Server size={16} style={{ color: "var(--accent-blue)" }} /> About AlgoTrade
            </span>
            <span style={{ fontSize: "0.75rem", fontWeight: 700, padding: "0.15rem 0.5rem", borderRadius: "3px", backgroundColor: "rgba(59, 130, 246, 0.15)", color: "var(--accent-blue)" }}>
              v1.0.0
            </span>
          </div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", display: "flex", flexDirection: "column", gap: "0.4rem" }}>
            <div><strong>Operating Invariant:</strong> Pure Simulation &amp; Quantitative Research Laboratory. Zero live brokerage connections or order endpoints.</div>
            <div><strong>Supported Modes:</strong> <code>HISTORICAL_REPLAY</code>, <code>SYNTHETIC_STREAM</code>, <code>REAL_TIME</code>.</div>
            <div><strong>Backend API Version:</strong> 1.0.0 (FastAPI + Pydantic v2 + SQLite Engine).</div>
          </div>
        </div>

        {/* Save Button */}
        <div>
          <button type="submit" className="btn btn-primary">
            <Save size={16} /> Save Settings
          </button>
        </div>
      </form>
    </div>
  );
};
