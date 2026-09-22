import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  ShieldAlert,
  Play,
  Pause,
  SkipForward,
  Square,
  Plus,
  Activity,
  DollarSign,
  TrendingUp,
  Percent,
  Clock,
  Layers,
  FileText,
  Download,
  CheckCircle2,
  XCircle,
  Radio,
  Wifi,
  AlertTriangle,
} from "lucide-react";
import {
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  AreaChart,
  Area,
} from "recharts";

import {
  listPaperSessions,
  getPaperSession,
  createPaperSession,
  startPaperSession,
  pausePaperSession,
  resumePaperSession,
  stopPaperSession,
  stepPaperSession,
  changePaperSpeed,
  getPaperOrders,
  getPaperPositions,
  getPaperEvents,
  exportPaperResults,
  getPaperWebSocketUrl,
  getMarketProviders,
  getMarketStatus,
} from "../services/paper";
import { getApiBaseUrl } from "../services/api";
import { listDatasets } from "../services/datasets";
import { listStrategies } from "../services/strategies";
import {
  PaperTradingSessionSummary,
  PaperOrderRecord,
  PaperPositionRecord,
  PaperEventRecord,
  CreatePaperSessionPayload,
  DatasetMetadata,
  StrategyMetadata,
  MarketProviderInfo,
  MarketConnectionStatus,
} from "../types";
import { LoadingSpinner, ErrorMessage, StatusBadge, EmptyState } from "../components/Common";

export const PaperTradingPage: React.FC = () => {
  // Session list & active session
  const [sessions, setSessions] = useState<PaperTradingSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [session, setSession] = useState<PaperTradingSessionSummary | null>(null);

  // Detail states
  const [orders, setOrders] = useState<PaperOrderRecord[]>([]);
  const [positions, setPositions] = useState<PaperPositionRecord[]>([]);
  const [events, setEvents] = useState<PaperEventRecord[]>([]);
  const [priceHistory, setPriceHistory] = useState<Array<{ timestamp: string; price: number; bid?: number; ask?: number }>>([]);

  // Real-time market data feed & health states
  const [filterMode, setFilterMode] = useState<"ALL" | "HISTORICAL_REPLAY" | "SYNTHETIC_STREAM" | "REAL_TIME">("ALL");
  const [providerStatus, setProviderStatus] = useState<MarketConnectionStatus | null>(null);
  const [marketProviders, setMarketProviders] = useState<MarketProviderInfo[]>([]);

  // UI tabs & modals
  const [activeTab, setActiveTab] = useState<"market" | "positions" | "orders" | "events" | "analytics">("market");
  const [isNewModalOpen, setIsNewModalOpen] = useState(false);
  const [eventFilter, setEventFilter] = useState<string>("ALL");

  // Metadata for modal
  const [datasets, setDatasets] = useState<DatasetMetadata[]>([]);
  const [strategies, setStrategies] = useState<StrategyMetadata[]>([]);

  // Loading & error
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);

  // New session form state
  const [formMode, setFormMode] = useState<"HISTORICAL_REPLAY" | "SYNTHETIC_STREAM" | "REAL_TIME">("HISTORICAL_REPLAY");
  const [formLiveProvider, setFormLiveProvider] = useState<string>("alpaca");
  const [formSymbols, setFormSymbols] = useState<string>("AAPL");
  const [formBarInterval, setFormBarInterval] = useState<string>("1m");
  const [formMaxDataAge, setFormMaxDataAge] = useState<number>(15);
  const [formDataset, setFormDataset] = useState("AAPL");
  const [formStrategy, setFormStrategy] = useState("MovingAverageCross");
  const [formCapital, setFormCapital] = useState(100000);
  const [formSpeed, setFormSpeed] = useState("1x");
  const [formShorting, setFormShorting] = useState(false);
  const [formFastPeriod, setFormFastPeriod] = useState(10);
  const [formSlowPeriod, setFormSlowPeriod] = useState(30);
  const [formLookback, setFormLookback] = useState(20);

  const wsRef = useRef<WebSocket | null>(null);

  // Load initial session list & metadata
  const loadInitialData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [sList, dList, stratList, provs] = await Promise.all([
        listPaperSessions(),
        listDatasets(),
        listStrategies(),
        getMarketProviders().catch(() => []),
      ]);
      setSessions(sList);
      setDatasets(dList);
      setStrategies(stratList);
      setMarketProviders(provs);

      if (sList.length > 0) {
        setActiveSessionId(sList[0].session_id);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, []);

  // Fetch session details
  const fetchSessionDetails = useCallback(async (sid: string) => {
    try {
      const [sess, ords, pos, evts] = await Promise.all([
        getPaperSession(sid),
        getPaperOrders(sid),
        getPaperPositions(sid),
        getPaperEvents(sid, 100),
      ]);
      setSession(sess);
      setOrders(ords);
      setPositions(pos);
      setEvents(evts);

      if (sess.mode === "REAL_TIME") {
        getMarketStatus().then(setProviderStatus).catch(() => {});
      }

      // Extract price trajectory from market events
      const prices = evts
        .filter((e) => (e.event_type === "MARKET_BAR" || e.event_type === "MARKET_UPDATE") && e.close)
        .map((e) => ({
          timestamp: (e.timestamp || "").includes("T") ? (e.timestamp || "").split("T")[1].slice(0, 8) : (e.timestamp || "").split("T")[0],
          price: e.close as number,
          bid: e.bid,
          ask: e.ask,
        }));
      if (prices.length > 0) {
        setPriceHistory(prices.slice(-100));
      }
    } catch (err) {
      console.error("Error fetching session details:", err);
    }
  }, []);

  // Update active session on selection
  useEffect(() => {
    if (activeSessionId) {
      fetchSessionDetails(activeSessionId);
    } else {
      setSession(null);
      setOrders([]);
      setPositions([]);
      setEvents([]);
      setPriceHistory([]);
    }
  }, [activeSessionId, fetchSessionDetails]);

  // WebSocket Connection
  useEffect(() => {
    if (!activeSessionId) return;

    const wsUrl = getPaperWebSocketUrl(activeSessionId);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event_type === "CONNECTED") {
          if (data.session) setSession(data.session);
          if (data.positions) setPositions(data.positions);
          if (data.orders) setOrders(data.orders);
          return;
        }

        // Handle streaming simulation events
        setEvents((prev) => [...prev.slice(-99), data]);

        if (data.event_type === "MARKET_BAR" || data.event_type === "MARKET_UPDATE") {
          if (data.close) {
            const timeLabel = (data.timestamp || "").includes("T")
              ? (data.timestamp || "").split("T")[1].slice(0, 8)
              : (data.timestamp || "").split("T")[0];
            setPriceHistory((prev) => [
              ...prev.slice(-99),
              {
                timestamp: timeLabel,
                price: data.close,
                bid: data.bid,
                ask: data.ask,
              },
            ]);
          }
          setSession((prev) =>
            prev
              ? {
                  ...prev,
                  current_bar_index: data.bar_index || prev.current_bar_index + 1,
                  simulation_timestamp: data.timestamp,
                  last_data_timestamp: data.timestamp,
                  latency_ms: data.latency_ms ?? prev.latency_ms,
                }
              : prev
          );
        } else if (data.event_type === "PROVIDER_STATUS") {
          setSession((prev) =>
            prev
              ? {
                  ...prev,
                  safety_state: data.safety_state,
                  latency_ms: data.latency_ms ?? prev.latency_ms,
                }
              : prev
          );
          setProviderStatus(data);
        } else if (data.event_type === "ORDER_FILLED" || data.event_type === "STOP_LOSS_TRIGGERED") {
          // Refresh orders & positions on fill
          getPaperOrders(activeSessionId).then(setOrders).catch(() => {});
          getPaperPositions(activeSessionId).then(setPositions).catch(() => {});
        } else if (data.event_type === "PORTFOLIO_SNAPSHOT") {
          setSession((prev) =>
            prev
              ? {
                  ...prev,
                  current_equity: data.total_equity ?? prev.current_equity,
                  cash: data.cash ?? prev.cash,
                  realized_pnl: data.realized_pnl ?? prev.realized_pnl,
                  unrealized_pnl: data.unrealized_pnl ?? prev.unrealized_pnl,
                  current_exposure: data.current_exposure ?? prev.current_exposure,
                }
              : prev
          );
        } else if (data.event_type === "SESSION_COMPLETED" || data.event_type === "SESSION_STOPPED") {
          setSession((prev) => (prev ? { ...prev, status: "STOPPED" } : prev));
        } else if (data.event_type === "SESSION_PAUSED") {
          setSession((prev) => (prev ? { ...prev, status: "PAUSED" } : prev));
        } else if (data.event_type === "SESSION_STARTED") {
          setSession((prev) => (prev ? { ...prev, status: "RUNNING" } : prev));
        }
      } catch (err) {
        console.error("WS parse error:", err);
      }
    };

    ws.onclose = () => {
      setWsConnected(false);
    };

    ws.onerror = () => {
      setWsConnected(false);
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [activeSessionId]);

  // Polling fallback when running if WebSocket is disconnected
  useEffect(() => {
    if (!session || session.status !== "RUNNING" || wsConnected || !activeSessionId) return;

    const interval = setInterval(() => {
      fetchSessionDetails(activeSessionId);
    }, 2000);

    return () => clearInterval(interval);
  }, [session, wsConnected, activeSessionId, fetchSessionDetails]);

  // Session Control Actions
  const handleStartResume = async () => {
    if (!activeSessionId) return;
    setActionLoading(true);
    try {
      const updated = session?.status === "PAUSED"
        ? await resumePaperSession(activeSessionId)
        : await startPaperSession(activeSessionId);
      setSession(updated);
      setSessions((prev) => prev.map((s) => (s.session_id === activeSessionId ? updated : s)));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setActionLoading(false);
    }
  };

  const handlePause = async () => {
    if (!activeSessionId) return;
    setActionLoading(true);
    try {
      const updated = await pausePaperSession(activeSessionId);
      setSession(updated);
      setSessions((prev) => prev.map((s) => (s.session_id === activeSessionId ? updated : s)));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleStop = async () => {
    if (!activeSessionId) return;
    setActionLoading(true);
    try {
      const updated = await stopPaperSession(activeSessionId);
      setSession(updated);
      setSessions((prev) => prev.map((s) => (s.session_id === activeSessionId ? updated : s)));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleStep = async () => {
    if (!activeSessionId) return;
    setActionLoading(true);
    try {
      const res = await stepPaperSession(activeSessionId);
      setSession(res.session);
      setSessions((prev) => prev.map((s) => (s.session_id === activeSessionId ? res.session : s)));
      fetchSessionDetails(activeSessionId);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setActionLoading(false);
    }
  };

  const handleSpeedChange = async (speed: string) => {
    if (!activeSessionId) return;
    try {
      const updated = await changePaperSpeed(activeSessionId, speed);
      setSession(updated);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const handleExportTradesCsv = () => {
    if (!activeSessionId) return;
    window.open(`${getApiBaseUrl()}/paper/sessions/${activeSessionId}/export/trades.csv`, "_blank");
  };

  const handleExportEquityCsv = () => {
    if (!activeSessionId) return;
    window.open(`${getApiBaseUrl()}/paper/sessions/${activeSessionId}/export/equity.csv`, "_blank");
  };

  // Create New Session
  const handleCreateSession = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading(true);
    setError(null);
    try {
      let params: Record<string, any> = {};
      if (formStrategy === "MovingAverageCross") {
        params = { fast_period: Number(formFastPeriod), slow_period: Number(formSlowPeriod) };
      } else if (formStrategy === "TimeSeriesMomentum") {
        params = { lookback_period: Number(formLookback), entry_threshold: 0.02, exit_threshold: -0.01 };
      } else if (formStrategy === "MeanReversion") {
        params = { lookback_period: Number(formLookback), entry_zscore: 2.0, exit_zscore: 0.0 };
      } else if (formStrategy === "PairsTrading") {
        params = { lookback_period: 20, entry_threshold: 2.0, exit_threshold: 0.5 };
      }

      const symList = formMode !== "HISTORICAL_REPLAY"
        ? formSymbols.split(",").map((s) => s.trim().toUpperCase()).filter(Boolean)
        : [formDataset];

      const payload: CreatePaperSessionPayload = {
        dataset_id: formMode === "HISTORICAL_REPLAY" ? formDataset : (symList[0] || "AAPL"),
        symbols: symList.length > 0 ? symList : ["AAPL"],
        strategy: formStrategy,
        strategy_params: params,
        initial_capital: Number(formCapital),
        speed: formSpeed,
        allow_shorting: formShorting,
        mode: formMode,
        data_provider: formMode === "HISTORICAL_REPLAY" ? "HISTORICAL" : (formMode === "SYNTHETIC_STREAM" ? "SYNTHETIC_STREAM" : "LIVE_PROVIDER"),
        live_provider: formMode === "REAL_TIME" ? formLiveProvider : (formMode === "SYNTHETIC_STREAM" ? "mock" : undefined),
        bar_interval: formBarInterval,
        max_data_age_seconds: Number(formMaxDataAge) || 15.0,
      };

      const newSess = await createPaperSession(payload);
      setSessions((prev) => [newSess, ...prev]);
      setActiveSessionId(newSess.session_id);
      setIsNewModalOpen(false);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setActionLoading(false);
    }
  };

  // Export Results
  const handleExport = async () => {
    if (!activeSessionId) return;
    try {
      const res = await exportPaperResults(activeSessionId);
      // Trigger download
      const blob = new Blob([JSON.stringify(res, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `paper_session_${activeSessionId}_results.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  if (loading) {
    return <LoadingSpinner message="Initializing paper trading console..." />;
  }

  const pnlPercent = session
    ? (((session.current_equity - session.initial_capital) / session.initial_capital) * 100).toFixed(2)
    : "0.00";
  const isPositive = Number(pnlPercent) >= 0;
  const progressPct = session && session.total_bars > 0
    ? Math.min(100, Math.round((session.current_bar_index / session.total_bars) * 100))
    : 0;

  const filteredEvents = events.filter((e) => {
    if (eventFilter === "ALL") return true;
    if (eventFilter === "ORDERS") return e.event_type.includes("ORDER");
    if (eventFilter === "SIGNALS") return e.event_type.includes("SIGNAL");
    if (eventFilter === "RISK") return e.event_type.includes("RISK");
    if (eventFilter === "MARKET") return e.event_type.includes("MARKET");
    return true;
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem" }}>
        <div>
          <h1 style={{ fontSize: "1.25rem", fontWeight: 700, letterSpacing: "-0.01em" }}>
            Live Paper Trading Console
          </h1>
          <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
            Deterministic simulated order execution with authoritative risk controls & real-time telemetry
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
          {/* Data Source Switcher */}
          <div style={{ display: "flex", borderRadius: "4px", overflow: "hidden", border: "1px solid var(--border-subtle)" }}>
            <button
              onClick={() => setFilterMode("ALL")}
              style={{
                padding: "0.35rem 0.65rem",
                fontSize: "0.75rem",
                background: filterMode === "ALL" ? "var(--bg-card-hover)" : "var(--bg-surface)",
                color: filterMode === "ALL" ? "var(--accent-blue)" : "var(--text-secondary)",
                border: "none",
                cursor: "pointer",
                fontWeight: filterMode === "ALL" ? 600 : 400,
              }}
            >
              All Feeds
            </button>
            <button
              onClick={() => setFilterMode("HISTORICAL_REPLAY")}
              style={{
                padding: "0.35rem 0.65rem",
                fontSize: "0.75rem",
                background: filterMode === "HISTORICAL_REPLAY" ? "var(--bg-card-hover)" : "var(--bg-surface)",
                color: filterMode === "HISTORICAL_REPLAY" ? "var(--accent-blue)" : "var(--text-secondary)",
                borderLeft: "1px solid var(--border-subtle)",
                borderRight: "1px solid var(--border-subtle)",
                borderTop: "none",
                borderBottom: "none",
                cursor: "pointer",
                fontWeight: filterMode === "HISTORICAL_REPLAY" ? 600 : 400,
              }}
            >
              Historical Replay
            </button>
            <button
              onClick={() => setFilterMode("SYNTHETIC_STREAM")}
              style={{
                padding: "0.35rem 0.65rem",
                fontSize: "0.75rem",
                background: filterMode === "SYNTHETIC_STREAM" ? "var(--bg-card-hover)" : "var(--bg-surface)",
                color: filterMode === "SYNTHETIC_STREAM" ? "var(--status-amber)" : "var(--text-secondary)",
                borderRight: "1px solid var(--border-subtle)",
                borderLeft: "none",
                borderTop: "none",
                borderBottom: "none",
                cursor: "pointer",
                fontWeight: filterMode === "SYNTHETIC_STREAM" ? 600 : 400,
              }}
            >
              ⚡ Synthetic Stream
            </button>
            <button
              onClick={() => setFilterMode("REAL_TIME")}
              style={{
                padding: "0.35rem 0.65rem",
                fontSize: "0.75rem",
                background: filterMode === "REAL_TIME" ? "var(--bg-card-hover)" : "var(--bg-surface)",
                color: filterMode === "REAL_TIME" ? "var(--status-green)" : "var(--text-secondary)",
                border: "none",
                cursor: "pointer",
                fontWeight: filterMode === "REAL_TIME" ? 600 : 400,
              }}
            >
              ● Real-Time
            </button>
          </div>

          {/* Active Session Dropdown */}
          <select
            className="input-field"
            style={{ width: "240px", fontSize: "0.8125rem" }}
            value={activeSessionId || ""}
            onChange={(e) => setActiveSessionId(e.target.value)}
          >
            {sessions
              .filter((s) => filterMode === "ALL" || (s.mode || "HISTORICAL_REPLAY") === filterMode)
              .map((s) => (
                <option key={s.session_id} value={s.session_id}>
                  {s.session_id} ({s.mode === "REAL_TIME" ? "LIVE" : s.mode === "SYNTHETIC_STREAM" ? "SYNTH" : "HIST"} - {s.strategy})
                </option>
              ))}
          </select>

          <button
            onClick={() => setIsNewModalOpen(true)}
            className="btn btn-primary btn-sm"
            style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}
          >
            <Plus size={15} /> New Session
          </button>
        </div>
      </div>

      {/* Prominent Safety & Simulation Warning */}
      <div
        style={{
          backgroundColor: session?.mode === "REAL_TIME" ? "rgba(234, 179, 8, 0.08)" : session?.mode === "SYNTHETIC_STREAM" ? "rgba(168, 85, 247, 0.08)" : "rgba(239, 68, 68, 0.08)",
          border: session?.mode === "REAL_TIME" ? "1px solid rgba(234, 179, 8, 0.3)" : session?.mode === "SYNTHETIC_STREAM" ? "1px solid rgba(168, 85, 247, 0.3)" : "1px solid rgba(239, 68, 68, 0.3)",
          borderRadius: "6px",
          padding: "0.875rem 1.25rem",
          display: "flex",
          alignItems: "center",
          gap: "1rem",
        }}
      >
        <ShieldAlert size={26} style={{ color: session?.mode === "REAL_TIME" ? "var(--status-amber)" : session?.mode === "SYNTHETIC_STREAM" ? "#c084fc" : "var(--status-red)", flexShrink: 0 }} />
        <div>
          <div style={{ fontWeight: 800, fontSize: "0.875rem", color: session?.mode === "REAL_TIME" ? "var(--status-amber)" : session?.mode === "SYNTHETIC_STREAM" ? "#c084fc" : "var(--status-red)", letterSpacing: "0.04em" }}>
            {session?.mode === "REAL_TIME"
              ? "PAPER TRADING — REAL-TIME MARKET DATA — NO REAL MONEY / BROKERAGE ORDERS"
              : session?.mode === "SYNTHETIC_STREAM"
              ? "PAPER TRADING — SYNTHETIC TEST FEED — LOCAL DETERMINISTIC SIMULATION"
              : "PAPER TRADING ENVIRONMENT — NO REAL MONEY"}
          </div>
          <div style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", marginTop: "0.15rem" }}>
            {session?.mode === "REAL_TIME"
              ? "Prices are fed from real-time market data providers (e.g. Alpaca v2). Zero real-money or brokerage execution. All order fills, positions, and risk rules terminate in SimulatedBroker."
              : session?.mode === "SYNTHETIC_STREAM"
              ? "Market events are generated by local in-memory streaming simulator labeled SYNTHETIC TEST FEED. Zero external network calls."
              : "All orders, capital balances, and executions are strictly simulated in-memory. Brokerage API connections are disabled by architecture invariants."}
          </div>
        </div>
      </div>

      {/* Real-Time / Synthetic Feed Telemetry Card */}
      {session && (session.mode === "REAL_TIME" || session.mode === "SYNTHETIC_STREAM") && (
        <div
          style={{
            backgroundColor: "var(--bg-surface)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "6px",
            padding: "1rem 1.25rem",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "1rem",
            alignItems: "center",
          }}
        >
          <div>
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>FEED PROVIDER & MODE</div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.25rem" }}>
              <Radio size={16} style={{ color: session.mode === "SYNTHETIC_STREAM" ? "#c084fc" : "var(--status-green)" }} />
              <strong style={{ fontSize: "0.95rem" }}>
                {session.mode === "SYNTHETIC_STREAM" ? "SYNTHETIC TEST FEED" : (session.provider || "Alpaca Markets v2")}
              </strong>
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
              Symbols: <strong>{session.symbols.join(", ")}</strong> | Bar: <strong>{session.bar_interval || "1m"}</strong>
            </div>
          </div>

          <div>
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>FEED CONNECTION</div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.25rem" }}>
              <span
                style={{
                  width: "9px",
                  height: "9px",
                  borderRadius: "50%",
                  backgroundColor:
                    providerStatus?.state === "NOT_CONFIGURED"
                      ? "var(--status-red)"
                      : providerStatus?.state === "STALE"
                      ? "var(--status-amber)"
                      : (providerStatus?.connected ?? true)
                      ? "var(--status-green)"
                      : "var(--status-red)",
                }}
              />
              <span style={{ fontWeight: 700, fontSize: "0.875rem" }}>
                {providerStatus?.state || (session.status === "RUNNING" ? "CONNECTED" : "STANDBY")}
              </span>
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
              Reconnects: {providerStatus?.reconnect_count ?? 0}
              {providerStatus?.api_key_configured === false && (
                <span style={{ color: "var(--status-amber)", marginLeft: "0.5rem" }}>(API key missing)</span>
              )}
            </div>
          </div>

          <div>
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>SIGNAL SAFETY STATE</div>
            <div style={{ marginTop: "0.25rem" }}>
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.35rem",
                  padding: "0.25rem 0.6rem",
                  borderRadius: "4px",
                  fontSize: "0.75rem",
                  fontWeight: 700,
                  backgroundColor:
                    session.safety_state === "SIGNALS_PAUSED"
                      ? "rgba(234, 179, 8, 0.15)"
                      : "rgba(34, 197, 94, 0.15)",
                  color:
                    session.safety_state === "SIGNALS_PAUSED"
                      ? "var(--status-amber)"
                      : "var(--status-green)",
                }}
              >
                {session.safety_state === "SIGNALS_PAUSED" ? (
                  <>
                    <AlertTriangle size={13} /> SIGNALS PAUSED (STALE / STANDBY)
                  </>
                ) : (
                  <>
                    <CheckCircle2 size={13} /> SIGNALS ACTIVE (FRESH DATA)
                  </>
                )}
              </span>
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
              Decision: <strong>{session.decision_source || "RULE_BASED"}</strong>
            </div>
          </div>

          <div>
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>FEED LATENCY & HEARTBEAT</div>
            <div style={{ fontSize: "1.1rem", fontWeight: 700, marginTop: "0.25rem" }} className="mono">
              {session.latency_ms !== null && session.latency_ms !== undefined
                ? `${session.latency_ms.toFixed(1)} ms`
                : "< 1.5 ms"}
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
              Last Tick: {session.last_data_timestamp ? session.last_data_timestamp.slice(-8) : "Active"}
            </div>
          </div>
        </div>
      )}

      {error && <ErrorMessage message={error} onRetry={() => setError(null)} />}

      {/* Replay Control HUD Bar */}
      {session ? (
        <div
          style={{
            backgroundColor: "var(--bg-surface)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "6px",
            padding: "1rem 1.25rem",
            display: "flex",
            flexDirection: "column",
            gap: "0.875rem",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
            {/* Playback action buttons */}
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              {session.status === "RUNNING" ? (
                <button
                  onClick={handlePause}
                  disabled={actionLoading}
                  className="btn btn-secondary btn-sm"
                  style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}
                >
                  <Pause size={14} /> Pause
                </button>
              ) : (
                <button
                  onClick={handleStartResume}
                  disabled={actionLoading || session.status === "STOPPED"}
                  className="btn btn-primary btn-sm"
                  style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}
                >
                  <Play size={14} /> {session.mode === "REAL_TIME" ? (session.status === "PAUSED" ? "Resume Stream" : "Start Live Feed") : (session.status === "PAUSED" ? "Resume" : "Start Replay")}
                </button>
              )}

              {session.mode !== "REAL_TIME" && (
                <button
                  onClick={handleStep}
                  disabled={actionLoading || session.status === "RUNNING" || session.status === "STOPPED"}
                  className="btn btn-secondary btn-sm"
                  title="Advance simulation by 1 historical bar"
                  style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}
                >
                  <SkipForward size={14} /> Step 1 Bar
                </button>
              )}

              <button
                onClick={handleStop}
                disabled={actionLoading || session.status === "STOPPED"}
                className="btn btn-secondary btn-sm"
                style={{ display: "flex", alignItems: "center", gap: "0.35rem", color: "var(--status-red)" }}
              >
                <Square size={14} /> Stop
              </button>

              {/* Speed selector */}
              {session.mode !== "REAL_TIME" ? (
                <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginLeft: "0.5rem" }}>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>SPEED:</span>
                  <select
                    value={session.speed}
                    onChange={(e) => handleSpeedChange(e.target.value)}
                    className="input-field"
                    style={{ width: "80px", padding: "0.25rem 0.5rem", fontSize: "0.75rem" }}
                  >
                    <option value="0.5x">0.5x</option>
                    <option value="1x">1x</option>
                    <option value="2x">2x</option>
                    <option value="5x">5x</option>
                    <option value="10x">10x</option>
                    <option value="MAX">MAX</option>
                  </select>
                </div>
              ) : (
                <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginLeft: "0.5rem", fontSize: "0.75rem", color: "var(--status-green)", fontWeight: 600 }}>
                  <Wifi size={13} /> STREAMING (REAL-TIME)
                </div>
              )}

              {/* CSV Exports */}
              <div style={{ display: "flex", alignItems: "center", gap: "0.35rem", marginLeft: "0.5rem" }}>
                <button
                  onClick={handleExportTradesCsv}
                  className="btn btn-secondary btn-sm"
                  title="Download closed trades as CSV"
                  style={{ display: "flex", alignItems: "center", gap: "0.3rem", fontSize: "0.75rem", padding: "0.25rem 0.5rem" }}
                >
                  <Download size={13} /> Trades CSV
                </button>
                <button
                  onClick={handleExportEquityCsv}
                  className="btn btn-secondary btn-sm"
                  title="Download equity curve as CSV"
                  style={{ display: "flex", alignItems: "center", gap: "0.3rem", fontSize: "0.75rem", padding: "0.25rem 0.5rem" }}
                >
                  <Download size={13} /> Equity CSV
                </button>
              </div>
            </div>

            {/* Status & WebSocket indicator */}
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.75rem" }}>
                <span
                  style={{
                    width: "8px",
                    height: "8px",
                    borderRadius: "50%",
                    backgroundColor: wsConnected ? "var(--status-green)" : "var(--status-amber)",
                  }}
                />
                <span style={{ color: "var(--text-muted)" }}>{wsConnected ? "WS Stream Live" : "Polling"}</span>
              </div>
              <StatusBadge status={session.status} />
            </div>
          </div>

          {/* Progress bar */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "var(--text-secondary)", marginBottom: "0.35rem" }}>
              {session.mode === "REAL_TIME" ? (
                <>
                  <span>Live Feed Ticks: <strong>{session.current_bar_index}</strong> received</span>
                  <span>Last Tick: <strong>{session.last_data_timestamp || session.simulation_timestamp || "Awaiting stream..."}</strong></span>
                </>
              ) : (
                <>
                  <span>
                    Replay Progress: <strong>{session.current_bar_index}</strong> / {session.total_bars} bars ({progressPct}%)
                  </span>
                  <span className="mono">
                    Date: {session.simulation_timestamp ? session.simulation_timestamp.split("T")[0] : "Pending start"}
                  </span>
                </>
              )}
            </div>
            {session.mode !== "REAL_TIME" && (
              <div style={{ width: "100%", height: "6px", backgroundColor: "var(--bg-app)", borderRadius: "3px", overflow: "hidden" }}>
                <div
                  style={{
                    width: `${progressPct}%`,
                    height: "100%",
                    backgroundColor: "var(--accent-blue)",
                    transition: "width 0.2s ease",
                  }}
                />
              </div>
            )}
          </div>
        </div>
      ) : (
        <EmptyState
          title="No Active Paper Session"
          message="Select an existing session from the dropdown above or click 'New Session' to begin simulated replay."
        />
      )}

      {/* Real-time Virtual Account Metrics Grid */}
      {session && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.875rem" }}>
          {/* Current Equity */}
          <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "6px", padding: "1rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", color: "var(--text-muted)", fontSize: "0.75rem" }}>
              <span>TOTAL EQUITY</span>
              <DollarSign size={15} />
            </div>
            <div style={{ fontSize: "1.35rem", fontWeight: 700, marginTop: "0.35rem" }} className="mono">
              ${session.current_equity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div style={{ fontSize: "0.75rem", marginTop: "0.2rem", color: isPositive ? "var(--status-green)" : "var(--status-red)" }}>
              {isPositive ? "+" : ""}{pnlPercent}% vs Capital
            </div>
          </div>

          {/* Available Cash */}
          <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "6px", padding: "1rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", color: "var(--text-muted)", fontSize: "0.75rem" }}>
              <span>VIRTUAL CASH</span>
              <Activity size={15} />
            </div>
            <div style={{ fontSize: "1.35rem", fontWeight: 700, marginTop: "0.35rem" }} className="mono">
              ${session.cash.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div style={{ fontSize: "0.75rem", marginTop: "0.2rem", color: "var(--text-muted)" }}>
              Initial: ${session.initial_capital.toLocaleString()}
            </div>
          </div>

          {/* Realized P&L */}
          <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "6px", padding: "1rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", color: "var(--text-muted)", fontSize: "0.75rem" }}>
              <span>REALIZED P&L</span>
              <TrendingUp size={15} />
            </div>
            <div
              style={{
                fontSize: "1.35rem",
                fontWeight: 700,
                marginTop: "0.35rem",
                color: session.realized_pnl >= 0 ? "var(--status-green)" : "var(--status-red)",
              }}
              className="mono"
            >
              {session.realized_pnl >= 0 ? "+" : ""}${session.realized_pnl.toFixed(2)}
            </div>
            <div style={{ fontSize: "0.75rem", marginTop: "0.2rem", color: "var(--text-muted)" }}>
              Closed positions
            </div>
          </div>

          {/* Unrealized P&L */}
          <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "6px", padding: "1rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", color: "var(--text-muted)", fontSize: "0.75rem" }}>
              <span>UNREALIZED P&L</span>
              <Clock size={15} />
            </div>
            <div
              style={{
                fontSize: "1.35rem",
                fontWeight: 700,
                marginTop: "0.35rem",
                color: session.unrealized_pnl >= 0 ? "var(--status-green)" : "var(--status-red)",
              }}
              className="mono"
            >
              {session.unrealized_pnl >= 0 ? "+" : ""}${session.unrealized_pnl.toFixed(2)}
            </div>
            <div style={{ fontSize: "0.75rem", marginTop: "0.2rem", color: "var(--text-muted)" }}>
              Open mark-to-market
            </div>
          </div>

          {/* Market Exposure */}
          <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "6px", padding: "1rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", color: "var(--text-muted)", fontSize: "0.75rem" }}>
              <span>EXPOSURE</span>
              <Percent size={15} />
            </div>
            <div style={{ fontSize: "1.35rem", fontWeight: 700, marginTop: "0.35rem" }} className="mono">
              {(session.current_exposure * 100).toFixed(1)}%
            </div>
            <div style={{ fontSize: "0.75rem", marginTop: "0.2rem", color: "var(--text-muted)" }}>
              {positions.length} active position{positions.length === 1 ? "" : "s"}
            </div>
          </div>
        </div>
      )}

      {/* Navigation Tabs */}
      {session && (
        <div style={{ display: "flex", borderBottom: "1px solid var(--border-subtle)", gap: "0.5rem" }}>
          {[
            { id: "market", label: "Live Market Chart", icon: Activity },
            { id: "positions", label: `Positions (${positions.length})`, icon: Layers },
            { id: "orders", label: `Orders (${orders.length})`, icon: FileText },
            { id: "events", label: `Event Stream (${events.length})`, icon: Clock },
            { id: "analytics", label: "Results & Export", icon: Download },
          ].map((tab) => {
            const Icon = tab.icon;
            const isSel = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                style={{
                  padding: "0.6rem 1rem",
                  fontSize: "0.8125rem",
                  fontWeight: isSel ? 600 : 400,
                  color: isSel ? "var(--text-primary)" : "var(--text-secondary)",
                  borderBottom: isSel ? "2px solid var(--accent-blue)" : "2px solid transparent",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.4rem",
                  background: "none",
                  cursor: "pointer",
                }}
              >
                <Icon size={14} /> {tab.label}
              </button>
            );
          })}
        </div>
      )}

      {/* Tab Content */}
      {session && (
        <div>
          {/* TAB 1: Market Chart */}
          {activeTab === "market" && (
            <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "6px", padding: "1.25rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <div>
                  <h3 style={{ fontSize: "0.95rem", fontWeight: 700 }}>
                    {session.mode === "REAL_TIME" ? "Live Market Stream" : "Simulated Price Action"} — {session.symbols.join(" / ")}
                  </h3>
                  <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                    {session.mode === "REAL_TIME"
                      ? "Bounded streaming observation window with real-time quote tracking & execution markers"
                      : "Bar-by-bar progression synchronized with zero lookahead bias"}
                  </p>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "0.8125rem", fontWeight: 700 }} className="mono">
                    {priceHistory.length > 0
                      ? `Latest: $${priceHistory[priceHistory.length - 1].price.toFixed(2)}`
                      : "Awaiting bars..."}
                  </div>
                  {priceHistory.length > 0 && priceHistory[priceHistory.length - 1].bid && (
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }} className="mono">
                      Bid: ${priceHistory[priceHistory.length - 1].bid?.toFixed(2)} | Ask: ${priceHistory[priceHistory.length - 1].ask?.toFixed(2)}
                    </div>
                  )}
                </div>
              </div>

              {priceHistory.length > 1 ? (
                <div style={{ height: "300px", width: "100%" }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={priceHistory}>
                      <defs>
                        <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                      <XAxis dataKey="timestamp" stroke="var(--text-muted)" fontSize={11} />
                      <YAxis stroke="var(--text-muted)" fontSize={11} domain={["auto", "auto"]} />
                      <Tooltip
                        contentStyle={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px" }}
                        formatter={(val: any) => [`$${Number(val).toFixed(2)}`, "Close Price"]}
                      />
                      <Area type="monotone" dataKey="price" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#priceGrad)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              ) : (
                <EmptyState title="No Chart Data Yet" message="Start replay or step the simulation to stream historical price bars." />
              )}
            </div>
          )}

          {/* TAB 2: Positions */}
          {activeTab === "positions" && (
            <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "6px", padding: "1.25rem" }}>
              <h3 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "1rem" }}>Current Open Positions</h3>
              {positions.length > 0 ? (
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", fontSize: "0.8125rem", borderCollapse: "collapse" }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--border-subtle)", textAlign: "left", color: "var(--text-muted)", fontSize: "0.75rem" }}>
                        <th style={{ padding: "0.5rem" }}>SYMBOL</th>
                        <th style={{ padding: "0.5rem" }}>DIRECTION</th>
                        <th style={{ padding: "0.5rem" }}>QUANTITY</th>
                        <th style={{ padding: "0.5rem" }}>AVG ENTRY</th>
                        <th style={{ padding: "0.5rem" }}>CURRENT PRICE</th>
                        <th style={{ padding: "0.5rem" }}>MARKET VALUE</th>
                        <th style={{ padding: "0.5rem" }}>UNREALIZED P&L</th>
                      </tr>
                    </thead>
                    <tbody>
                      {positions.map((p, idx) => (
                        <tr key={idx} style={{ borderBottom: "1px solid rgba(255,255,255,0.03)" }} className="mono">
                          <td style={{ padding: "0.6rem 0.5rem", fontWeight: 700 }}>{p.symbol}</td>
                          <td style={{ padding: "0.6rem 0.5rem" }}>
                            <StatusBadge status={p.direction} variant={p.direction === "LONG" ? "green" : "amber"} />
                          </td>
                          <td style={{ padding: "0.6rem 0.5rem" }}>{p.quantity}</td>
                          <td style={{ padding: "0.6rem 0.5rem" }}>${p.avg_entry_price.toFixed(2)}</td>
                          <td style={{ padding: "0.6rem 0.5rem" }}>${p.current_price.toFixed(2)}</td>
                          <td style={{ padding: "0.6rem 0.5rem" }}>${p.market_value.toFixed(2)}</td>
                          <td
                            style={{
                              padding: "0.6rem 0.5rem",
                              fontWeight: 700,
                              color: p.unrealized_pnl >= 0 ? "var(--status-green)" : "var(--status-red)",
                            }}
                          >
                            {p.unrealized_pnl >= 0 ? "+" : ""}${p.unrealized_pnl.toFixed(2)} ({(p.unrealized_pnl_pct * 100).toFixed(2)}%)
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <EmptyState title="No Open Positions" message="The strategy currently holds 100% cash balance." />
              )}
            </div>
          )}

          {/* TAB 3: Orders */}
          {activeTab === "orders" && (
            <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "6px", padding: "1.25rem" }}>
              <h3 style={{ fontSize: "0.95rem", fontWeight: 700, marginBottom: "1rem" }}>
                Simulated Orders & Risk Validation Log
              </h3>
              {orders.length > 0 ? (
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", fontSize: "0.8125rem", borderCollapse: "collapse" }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--border-subtle)", textAlign: "left", color: "var(--text-muted)", fontSize: "0.75rem" }}>
                        <th style={{ padding: "0.5rem" }}>ORDER ID</th>
                        <th style={{ padding: "0.5rem" }}>TIMESTAMP</th>
                        <th style={{ padding: "0.5rem" }}>SYMBOL</th>
                        <th style={{ padding: "0.5rem" }}>SIDE</th>
                        <th style={{ padding: "0.5rem" }}>QTY</th>
                        <th style={{ padding: "0.5rem" }}>FILL PRICE</th>
                        <th style={{ padding: "0.5rem" }}>COMM / SLIP</th>
                        <th style={{ padding: "0.5rem" }}>STATUS</th>
                        <th style={{ padding: "0.5rem" }}>DECISION SOURCE</th>
                        <th style={{ padding: "0.5rem" }}>RISK / REJECTION REASON</th>
                      </tr>
                    </thead>
                    <tbody>
                      {orders.map((o) => (
                        <tr key={o.order_id} style={{ borderBottom: "1px solid rgba(255,255,255,0.03)" }} className="mono">
                          <td style={{ padding: "0.6rem 0.5rem" }}>{o.order_id}</td>
                          <td style={{ padding: "0.6rem 0.5rem", fontSize: "0.75rem" }}>{o.timestamp.split("T")[0]}</td>
                          <td style={{ padding: "0.6rem 0.5rem", fontWeight: 700 }}>{o.symbol}</td>
                          <td style={{ padding: "0.6rem 0.5rem" }}>
                            <StatusBadge status={o.side} variant={o.side === "BUY" ? "green" : "red"} />
                          </td>
                          <td style={{ padding: "0.6rem 0.5rem" }}>{o.quantity}</td>
                          <td style={{ padding: "0.6rem 0.5rem" }}>{o.fill_price ? `$${o.fill_price.toFixed(2)}` : "—"}</td>
                          <td style={{ padding: "0.6rem 0.5rem", fontSize: "0.75rem", color: "var(--text-muted)" }}>
                            ${o.commission.toFixed(2)} / ${o.slippage.toFixed(2)}
                          </td>
                          <td style={{ padding: "0.6rem 0.5rem" }}>
                            <StatusBadge
                              status={o.status}
                              variant={o.status === "FILLED" ? "green" : o.status === "REJECTED" ? "red" : "amber"}
                            />
                          </td>
                          <td style={{ padding: "0.6rem 0.5rem", fontSize: "0.75rem" }}>
                            <span
                              style={{
                                padding: "0.15rem 0.4rem",
                                borderRadius: "3px",
                                fontWeight: 600,
                                backgroundColor:
                                  o.decision_source === "XGBOOST"
                                    ? "rgba(59, 130, 246, 0.15)"
                                    : o.decision_source === "JEV" || o.decision_source === "JEV_ASSISTED"
                                    ? "rgba(168, 85, 247, 0.15)"
                                    : "rgba(100, 116, 139, 0.15)",
                                color:
                                  o.decision_source === "XGBOOST"
                                    ? "var(--accent-blue)"
                                    : o.decision_source === "JEV" || o.decision_source === "JEV_ASSISTED"
                                    ? "#c084fc"
                                    : "var(--text-secondary)",
                              }}
                            >
                              {o.decision_source || "RULE_BASED"}
                              {o.model_version ? ` (${o.model_version})` : ""}
                            </span>
                          </td>
                          <td style={{ padding: "0.6rem 0.5rem", fontSize: "0.75rem", color: o.rejection_reason ? "var(--status-red)" : "var(--text-muted)" }}>
                            {o.rejection_reason || "Passed risk validation"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <EmptyState title="No Orders Submitted" message="The strategy has not emitted trade signals requiring execution yet." />
              )}
            </div>
          )}

          {/* TAB 4: Event Stream */}
          {activeTab === "events" && (
            <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "6px", padding: "1.25rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "0.5rem" }}>
                <h3 style={{ fontSize: "0.95rem", fontWeight: 700 }}>Chronological Simulation Audit Trail</h3>
                {/* Event Type Filter */}
                <div style={{ display: "flex", gap: "0.3rem" }}>
                  {["ALL", "ORDERS", "SIGNALS", "RISK", "MARKET"].map((f) => (
                    <button
                      key={f}
                      onClick={() => setEventFilter(f)}
                      className={`btn btn-sm ${eventFilter === f ? "btn-primary" : "btn-secondary"}`}
                      style={{ fontSize: "0.7rem", padding: "0.2rem 0.6rem" }}
                    >
                      {f}
                    </button>
                  ))}
                </div>
              </div>

              {filteredEvents.length > 0 ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", maxHeight: "400px", overflowY: "auto" }}>
                  {filteredEvents.slice().reverse().map((evt, idx) => (
                    <div
                      key={idx}
                      style={{
                        backgroundColor: "var(--bg-app)",
                        padding: "0.6rem 0.8rem",
                        borderRadius: "4px",
                        borderLeft: `3px solid ${
                          evt.event_type.includes("FILL")
                            ? "var(--status-green)"
                            : evt.event_type.includes("REJECT") || evt.event_type.includes("STOP")
                            ? "var(--status-red)"
                            : evt.event_type.includes("SIGNAL")
                            ? "var(--accent-blue)"
                            : "var(--border-strong)"
                        }`,
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        fontSize: "0.8125rem",
                      }}
                      className="mono"
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                        <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                          {(evt.timestamp || "").replace("T", " ")}
                        </span>
                        <span style={{ fontWeight: 700 }}>{evt.event_type}</span>
                        <span style={{ color: "var(--text-secondary)" }}>
                          {evt.symbol ? `[${evt.symbol}] ` : ""}
                          {evt.message ||
                            (evt.fill_price ? `Fill: $${evt.fill_price.toFixed(2)} (Qty: ${evt.quantity})` : "") ||
                            (evt.signal_type ? `Signal: ${evt.signal_type}` : "") ||
                            (evt.reason ? `Reason: ${evt.reason}` : "") ||
                            (evt.total_equity ? `Equity: $${evt.total_equity.toFixed(2)}` : "")}
                        </span>
                      </div>
                      {evt.approved !== undefined && (
                        <div>{evt.approved ? <CheckCircle2 size={16} color="var(--status-green)" /> : <XCircle size={16} color="var(--status-red)" />}</div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="No Events Recorded" message="Events will appear here as the simulation processes bars." />
              )}
            </div>
          )}

          {/* TAB 5: Results & Export */}
          {activeTab === "analytics" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "6px", padding: "1.25rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                  <div>
                    <h3 style={{ fontSize: "0.95rem", fontWeight: 700 }}>Performance Summary & Audit Export</h3>
                    <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                      Download complete execution log, equity points, and trade history as JSON
                    </p>
                  </div>
                  <button
                    onClick={handleExport}
                    className="btn btn-primary btn-sm"
                    style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}
                  >
                    <Download size={14} /> Export JSON Results
                  </button>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem", fontSize: "0.8125rem" }} className="mono">
                  <div style={{ backgroundColor: "var(--bg-app)", padding: "0.875rem", borderRadius: "4px" }}>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>INITIAL CAPITAL</div>
                    <div style={{ fontWeight: 700, fontSize: "1.1rem", marginTop: "0.2rem" }}>
                      ${session.initial_capital.toLocaleString()}
                    </div>
                  </div>
                  <div style={{ backgroundColor: "var(--bg-app)", padding: "0.875rem", borderRadius: "4px" }}>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>FINAL EQUITY</div>
                    <div style={{ fontWeight: 700, fontSize: "1.1rem", marginTop: "0.2rem" }}>
                      ${session.current_equity.toFixed(2)}
                    </div>
                  </div>
                  <div style={{ backgroundColor: "var(--bg-app)", padding: "0.875rem", borderRadius: "4px" }}>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>NET RETURN</div>
                    <div style={{ fontWeight: 700, fontSize: "1.1rem", marginTop: "0.2rem", color: isPositive ? "var(--status-green)" : "var(--status-red)" }}>
                      {isPositive ? "+" : ""}{pnlPercent}%
                    </div>
                  </div>
                  <div style={{ backgroundColor: "var(--bg-app)", padding: "0.875rem", borderRadius: "4px" }}>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>TOTAL ORDERS SUBMITTED</div>
                    <div style={{ fontWeight: 700, fontSize: "1.1rem", marginTop: "0.2rem" }}>{orders.length}</div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Modal: Create New Paper Trading Session */}
      {isNewModalOpen && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "1rem",
          }}
        >
          <div
            style={{
              backgroundColor: "var(--bg-surface)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "8px",
              width: "100%",
              maxWidth: "500px",
              padding: "1.5rem",
              display: "flex",
              flexDirection: "column",
              gap: "1.25rem",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={{ fontSize: "1.1rem", fontWeight: 700 }}>New Paper Trading Session</h2>
              <button
                onClick={() => setIsNewModalOpen(false)}
                style={{ background: "none", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "1.2rem" }}
              >
                ×
              </button>
            </div>

            <form onSubmit={handleCreateSession} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              {/* Data Feed Mode Selector */}
              <div>
                <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "0.25rem" }}>
                  DATA FEED MODE
                </label>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.4rem" }}>
                  <button
                    type="button"
                    onClick={() => setFormMode("HISTORICAL_REPLAY")}
                    style={{
                      padding: "0.45rem 0.25rem",
                      borderRadius: "4px",
                      fontSize: "0.72rem",
                      border: formMode === "HISTORICAL_REPLAY" ? "1px solid var(--accent-blue)" : "1px solid var(--border-subtle)",
                      background: formMode === "HISTORICAL_REPLAY" ? "var(--bg-card-hover)" : "var(--bg-surface)",
                      color: formMode === "HISTORICAL_REPLAY" ? "var(--accent-blue)" : "var(--text-secondary)",
                      cursor: "pointer",
                      fontWeight: formMode === "HISTORICAL_REPLAY" ? 600 : 400,
                    }}
                  >
                    Historical Replay
                  </button>
                  <button
                    type="button"
                    onClick={() => setFormMode("SYNTHETIC_STREAM")}
                    style={{
                      padding: "0.45rem 0.25rem",
                      borderRadius: "4px",
                      fontSize: "0.72rem",
                      border: formMode === "SYNTHETIC_STREAM" ? "1px solid var(--status-amber)" : "1px solid var(--border-subtle)",
                      background: formMode === "SYNTHETIC_STREAM" ? "var(--bg-card-hover)" : "var(--bg-surface)",
                      color: formMode === "SYNTHETIC_STREAM" ? "var(--status-amber)" : "var(--text-secondary)",
                      cursor: "pointer",
                      fontWeight: formMode === "SYNTHETIC_STREAM" ? 600 : 400,
                    }}
                  >
                    ⚡ Synthetic Feed
                  </button>
                  <button
                    type="button"
                    onClick={() => setFormMode("REAL_TIME")}
                    style={{
                      padding: "0.45rem 0.25rem",
                      borderRadius: "4px",
                      fontSize: "0.72rem",
                      border: formMode === "REAL_TIME" ? "1px solid var(--status-green)" : "1px solid var(--border-subtle)",
                      background: formMode === "REAL_TIME" ? "var(--bg-card-hover)" : "var(--bg-surface)",
                      color: formMode === "REAL_TIME" ? "var(--status-green)" : "var(--text-secondary)",
                      cursor: "pointer",
                      fontWeight: formMode === "REAL_TIME" ? 600 : 400,
                    }}
                  >
                    ● Real-Time Feed
                  </button>
                </div>
              </div>

              {/* Dataset selection if Historical, or Provider & Symbols if Real-Time / Synthetic */}
              {formMode === "HISTORICAL_REPLAY" ? (
                <div>
                  <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "0.25rem" }}>
                    HISTORICAL DATASET
                  </label>
                  <select
                    className="input-field"
                    value={formDataset}
                    onChange={(e) => setFormDataset(e.target.value)}
                    style={{ width: "100%" }}
                  >
                    {datasets.map((d) => (
                      <option key={d.dataset_id} value={d.dataset_id}>
                        {d.dataset_id} ({d.row_count} bars)
                      </option>
                    ))}
                  </select>
                </div>
              ) : formMode === "SYNTHETIC_STREAM" ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  <div style={{ fontSize: "0.75rem", padding: "0.5rem 0.75rem", borderRadius: "4px", backgroundColor: "rgba(168, 85, 247, 0.1)", border: "1px solid rgba(168, 85, 247, 0.25)", color: "#c084fc" }}>
                    <strong>SYNTHETIC TEST FEED:</strong> In-memory tick generator simulates ticks & builds bars with zero external vendor dependencies.
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "0.75rem" }}>
                    <div>
                      <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "0.25rem" }}>
                        SYMBOLS (COMMA-SEPARATED)
                      </label>
                      <input
                        type="text"
                        className="input-field"
                        value={formSymbols}
                        onChange={(e) => setFormSymbols(e.target.value)}
                        placeholder="AAPL, MSFT"
                        style={{ width: "100%" }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "0.25rem" }}>
                        BAR INTERVAL
                      </label>
                      <select
                        className="input-field"
                        value={formBarInterval}
                        onChange={(e) => setFormBarInterval(e.target.value)}
                        style={{ width: "100%" }}
                      >
                        <option value="1s">1 second</option>
                        <option value="1m">1 minute</option>
                        <option value="5m">5 minutes</option>
                        <option value="15m">15 minutes</option>
                        <option value="1h">1 hour</option>
                      </select>
                    </div>
                  </div>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  <div>
                    <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "0.25rem" }}>
                      STREAMING PROVIDER
                    </label>
                    <select
                      className="input-field"
                      value={formLiveProvider}
                      onChange={(e) => setFormLiveProvider(e.target.value)}
                      style={{ width: "100%" }}
                    >
                      {marketProviders.filter((p) => p.is_live).length > 0 ? (
                        marketProviders
                          .filter((p) => p.is_live)
                          .map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name} {p.status === "not_configured" || p.status === "unconfigured" ? "(Requires API Credentials)" : ""}
                            </option>
                          ))
                      ) : (
                        <>
                          <option value="alpaca">Alpaca Markets v2 (IEX Free / SIP)</option>
                          <option value="websocket">Generic WebSocket Live Feed</option>
                        </>
                      )}
                    </select>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr 1fr", gap: "0.75rem" }}>
                    <div>
                      <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "0.25rem" }}>
                        SYMBOLS
                      </label>
                      <input
                        type="text"
                        className="input-field"
                        value={formSymbols}
                        onChange={(e) => setFormSymbols(e.target.value)}
                        placeholder="AAPL, MSFT"
                        style={{ width: "100%" }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "0.25rem" }}>
                        BAR INTERVAL
                      </label>
                      <select
                        className="input-field"
                        value={formBarInterval}
                        onChange={(e) => setFormBarInterval(e.target.value)}
                        style={{ width: "100%" }}
                      >
                        <option value="1s">1 second</option>
                        <option value="1m">1 minute</option>
                        <option value="5m">5 minutes</option>
                        <option value="15m">15 minutes</option>
                        <option value="1h">1 hour</option>
                      </select>
                    </div>
                    <div>
                      <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "0.25rem" }}>
                        MAX AGE (S)
                      </label>
                      <input
                        type="number"
                        className="input-field"
                        value={formMaxDataAge}
                        onChange={(e) => setFormMaxDataAge(Number(e.target.value))}
                        min={1}
                        max={300}
                        style={{ width: "100%" }}
                      />
                    </div>
                  </div>
                </div>
              )}

              <div>
                <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "0.25rem" }}>
                  STRATEGY
                </label>
                <select
                  className="input-field"
                  value={formStrategy}
                  onChange={(e) => setFormStrategy(e.target.value)}
                  style={{ width: "100%" }}
                >
                  {strategies.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Dynamic parameters depending on strategy */}
              {formStrategy === "MovingAverageCross" && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                  <div>
                    <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "0.25rem" }}>
                      FAST PERIOD
                    </label>
                    <input
                      type="number"
                      className="input-field"
                      value={formFastPeriod}
                      onChange={(e) => setFormFastPeriod(Number(e.target.value))}
                      style={{ width: "100%" }}
                      min={1}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "0.25rem" }}>
                      SLOW PERIOD
                    </label>
                    <input
                      type="number"
                      className="input-field"
                      value={formSlowPeriod}
                      onChange={(e) => setFormSlowPeriod(Number(e.target.value))}
                      style={{ width: "100%" }}
                      min={2}
                    />
                  </div>
                </div>
              )}

              {(formStrategy === "TimeSeriesMomentum" || formStrategy === "MeanReversion") && (
                <div>
                  <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "0.25rem" }}>
                    LOOKBACK PERIOD
                  </label>
                  <input
                    type="number"
                    className="input-field"
                    value={formLookback}
                    onChange={(e) => setFormLookback(Number(e.target.value))}
                    style={{ width: "100%" }}
                    min={5}
                  />
                </div>
              )}

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
                <div>
                  <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "0.25rem" }}>
                    INITIAL CAPITAL ($)
                  </label>
                  <input
                    type="number"
                    className="input-field"
                    value={formCapital}
                    onChange={(e) => setFormCapital(Number(e.target.value))}
                    style={{ width: "100%" }}
                    min={1000}
                    step={1000}
                  />
                </div>
                <div>
                  <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "0.25rem" }}>
                    INITIAL REPLAY SPEED
                  </label>
                  <select
                    className="input-field"
                    value={formSpeed}
                    onChange={(e) => setFormSpeed(e.target.value)}
                    style={{ width: "100%" }}
                  >
                    <option value="0.5x">0.5x (Slow)</option>
                    <option value="1x">1x (Real-time)</option>
                    <option value="2x">2x</option>
                    <option value="5x">5x</option>
                    <option value="10x">10x</option>
                    <option value="MAX">MAX (Immediate)</option>
                  </select>
                </div>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <input
                  type="checkbox"
                  id="shorting-toggle"
                  checked={formShorting}
                  onChange={(e) => setFormShorting(e.target.checked)}
                />
                <label htmlFor="shorting-toggle" style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                  Allow Short Selling
                </label>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem", marginTop: "0.5rem" }}>
                <button
                  type="button"
                  onClick={() => setIsNewModalOpen(false)}
                  className="btn btn-secondary btn-sm"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="btn btn-primary btn-sm"
                >
                  Create Session
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
