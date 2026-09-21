import React, { useState, useEffect } from "react";
import { getJevStatus, evaluateJev } from "../services/ai";
import { listExperiments, getExperiment } from "../services/experiments";
import { JevStatus, JevDecision, ExperimentResult } from "../types";
import { LoadingSpinner, ErrorMessage, StatusBadge } from "../components/Common";
import { ShieldAlert, Zap } from "lucide-react";

export const JevLabPage: React.FC = () => {
  const [status, setStatus] = useState<JevStatus | null>(null);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [statusError, setStatusError] = useState<string | null>(null);

  // Market context evaluation form
  const [symbol, setSymbol] = useState("AAPL");
  const [currentPrice, setCurrentPrice] = useState<number>(185.50);
  const [rsi, setRsi] = useState<number>(62.4);
  const [sma20Dist, setSma20Dist] = useState<number>(0.015);
  const [volatility, setVolatility] = useState<number>(0.18);
  const [evaluating, setEvaluating] = useState(false);
  const [evalError, setEvalError] = useState<string | null>(null);
  const [evalDecision, setEvalDecision] = useState<JevDecision | null>(null);

  // Recent Jev Experiments
  const [jevExperiment, setJevExperiment] = useState<ExperimentResult | null>(null);

  const fetchStatus = async () => {
    setLoadingStatus(true);
    setStatusError(null);
    try {
      const s = await getJevStatus();
      setStatus(s);

      // Find any experiment that used Jev
      const exps = await listExperiments(20);
      for (const e of exps) {
        const id = String(e.experiment_id || "");
        if (id) {
          const detail = await getExperiment(id);
          if (detail.ai_decision_stats) {
            setJevExperiment(detail);
            break;
          }
        }
      }
    } catch (err) {
      setStatusError((err as Error).message);
    } finally {
      setLoadingStatus(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleEvaluateContext = async (e: React.FormEvent) => {
    e.preventDefault();
    setEvaluating(true);
    setEvalError(null);

    const contextPayload = {
      symbol,
      price: currentPrice,
      rsi_14: rsi,
      sma_distance_20: sma20Dist,
      rolling_volatility_20: volatility,
      timestamp: new Date().toISOString(),
    };

    try {
      const decision = await evaluateJev(contextPayload);
      setEvalDecision(decision);
    } catch (err) {
      setEvalError((err as Error).message);
    } finally {
      setEvaluating(false);
    }
  };

  if (loadingStatus) return <LoadingSpinner message="Checking Jev AI decision engine status..." />;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: "1.25rem", fontWeight: 700, letterSpacing: "-0.01em" }}>
          Jev AI Decision Lab
        </h1>
        <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
          Advisory LLM reasoning layer with deterministic caching, zero-lookahead prompt construction, and fail-safe execution
        </p>
      </div>

      {statusError && <ErrorMessage message={statusError} onRetry={fetchStatus} />}

      {/* Provider Status Cards */}
      {status && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem" }}>
          <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "0.25rem" }}>
              Provider Status
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.25rem" }}>
              <StatusBadge status={status.provider_status} />
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                {status.enabled ? "Active" : "Disabled"}
              </span>
            </div>
          </div>

          <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "0.25rem" }}>
              Configured Model
            </div>
            <div className="mono" style={{ fontSize: "1.1rem", fontWeight: 700 }}>
              {status.model || "None"}
            </div>
          </div>

          <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "0.25rem" }}>
              Min Confidence Gate
            </div>
            <div className="mono" style={{ fontSize: "1.1rem", fontWeight: 700 }}>
              {(status.min_confidence * 100).toFixed(0)}%
            </div>
          </div>

          <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", padding: "1rem", borderRadius: "4px" }}>
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "0.25rem" }}>
              API Timeout
            </div>
            <div className="mono" style={{ fontSize: "1.1rem", fontWeight: 700 }}>
              {status.timeout_seconds}s
            </div>
          </div>
        </div>
      )}

      {/* Security Disclaimer Banner */}
      <div style={{ backgroundColor: "rgba(59, 130, 246, 0.05)", border: "1px solid var(--border-strong)", borderRadius: "4px", padding: "0.75rem 1rem", fontSize: "0.75rem", display: "flex", alignItems: "center", gap: "0.75rem" }}>
        <ShieldAlert size={18} style={{ color: "var(--accent-blue)", flexShrink: 0 }} />
        <div>
          <strong>Strict Security Contract:</strong> API credentials are never exposed in browser requests or JavaScript bundles. Requests route securely through the authoritative FastAPI backend.
        </div>
      </div>

      {/* Structured Evaluation Interface */}
      <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem" }}>
        <h2 style={{ fontSize: "0.95rem", fontWeight: 600, marginBottom: "0.75rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
          <Zap size={16} style={{ color: "var(--accent-blue)" }} /> Zero-Lookahead Market Context Evaluator
        </h2>
        <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginBottom: "1rem" }}>
          Test how Jev reasons about sanitized market indicators strictly available at bar t.
        </p>

        <form onSubmit={handleEvaluateContext} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "1rem", marginBottom: "1rem" }}>
          <div>
            <label style={{ display: "block", fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Symbol</label>
            <input type="text" value={symbol} onChange={(e) => setSymbol(e.target.value)} style={{ width: "100%" }} />
          </div>
          <div>
            <label style={{ display: "block", fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>Current Price ($)</label>
            <input type="number" value={currentPrice} onChange={(e) => setCurrentPrice(Number(e.target.value))} step={0.1} style={{ width: "100%" }} />
          </div>
          <div>
            <label style={{ display: "block", fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>14-period RSI</label>
            <input type="number" value={rsi} onChange={(e) => setRsi(Number(e.target.value))} step={0.5} style={{ width: "100%" }} />
          </div>
          <div>
            <label style={{ display: "block", fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>SMA 20 Distance</label>
            <input type="number" value={sma20Dist} onChange={(e) => setSma20Dist(Number(e.target.value))} step={0.005} style={{ width: "100%" }} />
          </div>
          <div>
            <label style={{ display: "block", fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: "0.25rem" }}>20-period Volatility</label>
            <input type="number" value={volatility} onChange={(e) => setVolatility(Number(e.target.value))} step={0.01} style={{ width: "100%" }} />
          </div>
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <button type="submit" disabled={evaluating} className="btn btn-primary" style={{ width: "100%" }}>
              {evaluating ? "Evaluating..." : "EVALUATE CONTEXT"}
            </button>
          </div>
        </form>

        {evalError && <ErrorMessage message={evalError} />}

        {/* Structured Decision Output */}
        {evalDecision && (
          <div style={{ marginTop: "1rem", padding: "1rem", backgroundColor: "var(--bg-app)", borderRadius: "4px", border: "1px solid var(--border-strong)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Decision:</span>
                <span
                  className="mono"
                  style={{
                    fontSize: "1.25rem",
                    fontWeight: 800,
                    color:
                      evalDecision.decision === "BUY"
                        ? "var(--status-green)"
                        : evalDecision.decision === "SELL"
                        ? "var(--status-red)"
                        : "var(--text-secondary)",
                  }}
                >
                  {evalDecision.decision}
                </span>
                <StatusBadge status={evalDecision.source} variant={evalDecision.source === "live_api" ? "green" : "blue"} />
              </div>

              <div className="mono" style={{ fontSize: "0.75rem", color: "var(--text-secondary)", display: "flex", gap: "1rem" }}>
                <span>Confidence: <strong>{(evalDecision.confidence * 100).toFixed(1)}%</strong></span>
                <span>Latency: <strong>{evalDecision.latency_ms} ms</strong></span>
              </div>
            </div>

            <div style={{ fontSize: "0.8125rem", color: "var(--text-primary)", backgroundColor: "var(--bg-surface)", padding: "0.75rem", borderRadius: "4px", border: "1px solid var(--border-subtle)" }}>
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "0.25rem" }}>LLM Reasoning:</div>
              {evalDecision.reasoning}
            </div>
          </div>
        )}
      </div>

      {/* Jev Experiment Statistics View */}
      {jevExperiment && jevExperiment.ai_decision_stats && (
        <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <div>
              <h2 style={{ fontSize: "0.95rem", fontWeight: 700 }}>
                Jev Experiment Audit: {jevExperiment.experiment_id}
              </h2>
              <span className="mono" style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                Model: {jevExperiment.ai_decision_stats.model} · Mode: {jevExperiment.ai_decision_stats.provider_mode}
              </span>
            </div>
            <StatusBadge
              status={jevExperiment.ai_decision_stats.cache_hits > 0 ? "CACHED_JEV" : "LIVE_JEV"}
              variant="blue"
            />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: "0.75rem", marginBottom: "1rem" }} className="mono">
            <div style={{ backgroundColor: "var(--bg-app)", padding: "0.65rem", borderRadius: "4px" }}>
              <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>TOTAL DECISIONS</div>
              <div style={{ fontSize: "1.1rem", fontWeight: 700 }}>{jevExperiment.ai_decision_stats.total_decisions}</div>
            </div>
            <div style={{ backgroundColor: "var(--bg-app)", padding: "0.65rem", borderRadius: "4px" }}>
              <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>BUY SIGNALS</div>
              <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--status-green)" }}>{jevExperiment.ai_decision_stats.buy_count}</div>
            </div>
            <div style={{ backgroundColor: "var(--bg-app)", padding: "0.65rem", borderRadius: "4px" }}>
              <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>SELL SIGNALS</div>
              <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "var(--status-red)" }}>{jevExperiment.ai_decision_stats.sell_count}</div>
            </div>
            <div style={{ backgroundColor: "var(--bg-app)", padding: "0.65rem", borderRadius: "4px" }}>
              <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>HOLD SIGNALS</div>
              <div style={{ fontSize: "1.1rem", fontWeight: 700 }}>{jevExperiment.ai_decision_stats.hold_count}</div>
            </div>
            <div style={{ backgroundColor: "var(--bg-app)", padding: "0.65rem", borderRadius: "4px" }}>
              <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>AVG CONFIDENCE</div>
              <div style={{ fontSize: "1.1rem", fontWeight: 700 }}>{(jevExperiment.ai_decision_stats.avg_confidence * 100).toFixed(1)}%</div>
            </div>
            <div style={{ backgroundColor: "var(--bg-app)", padding: "0.65rem", borderRadius: "4px" }}>
              <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>CACHE HITS / MISSES</div>
              <div style={{ fontSize: "1.1rem", fontWeight: 700 }}>{jevExperiment.ai_decision_stats.cache_hits} / {jevExperiment.ai_decision_stats.cache_misses}</div>
            </div>
            <div style={{ backgroundColor: "var(--bg-app)", padding: "0.65rem", borderRadius: "4px" }}>
              <div style={{ fontSize: "0.65rem", color: "var(--text-muted)" }}>FALLBACKS</div>
              <div style={{ fontSize: "1.1rem", fontWeight: 700 }}>{jevExperiment.ai_decision_stats.fallbacks}</div>
            </div>
          </div>

          <div style={{ padding: "0.5rem 0.75rem", backgroundColor: "rgba(245, 158, 11, 0.08)", border: "1px solid rgba(245, 158, 11, 0.2)", borderRadius: "3px", fontSize: "0.75rem", color: "var(--status-amber)" }}>
            * Research Note: Advisory LLM decision metrics do not imply or prove trading profitability. Execution outcomes depend strictly on market slippage, commissions, and risk limits.
          </div>
        </div>
      )}
    </div>
  );
};
