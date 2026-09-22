import React, { useState, useEffect } from "react";
import {
  LayoutDashboard,
  PlayCircle,
  Cpu,
  FlaskConical,
  Database,
  Binary,
  Sparkles,
  GitCompare,
  Briefcase,
  ScrollText,
  Settings,
  Activity,
  ShieldAlert,
  LucideIcon,
} from "lucide-react";
import { getApiBaseUrl } from "../services/api";

export type NavRoute =
  | "dashboard"
  | "backtests"
  | "strategies"
  | "experiments"
  | "datasets"
  | "ml-lab"
  | "jev-lab"
  | "comparison"
  | "portfolio"
  | "paper-trade"
  | "settings";

interface LayoutProps {
  currentRoute: NavRoute;
  onRouteChange: (route: NavRoute) => void;
  children: React.ReactNode;
}

const NAV_ITEMS: { route: NavRoute; label: string; icon: LucideIcon }[] = [
  { route: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { route: "backtests", label: "Backtests", icon: PlayCircle },
  { route: "strategies", label: "Strategies", icon: Cpu },
  { route: "experiments", label: "Experiments", icon: FlaskConical },
  { route: "datasets", label: "Datasets", icon: Database },
  { route: "ml-lab", label: "ML Lab", icon: Binary },
  { route: "jev-lab", label: "Jev Lab", icon: Sparkles },
  { route: "comparison", label: "Comparison", icon: GitCompare },
  { route: "portfolio", label: "Portfolio", icon: Briefcase },
  { route: "paper-trade", label: "Paper Trade", icon: ScrollText },
  { route: "settings", label: "Settings", icon: Settings },
];

export const Layout: React.FC<LayoutProps> = ({
  currentRoute,
  onRouteChange,
  children,
}) => {
  const [backendStatus, setBackendStatus] = useState<"checking" | "online" | "offline">("checking");
  const [currentTime, setCurrentTime] = useState<string>("");

  useEffect(() => {
    // Clock
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(now.toUTCString().slice(17, 25) + " UTC");
    };
    updateTime();
    const clockInterval = setInterval(updateTime, 1000);

    // Health check
    const checkHealth = async () => {
      try {
        const res = await fetch(`${getApiBaseUrl()}/health`);
        if (res.ok) {
          setBackendStatus("online");
        } else {
          setBackendStatus("offline");
        }
      } catch {
        setBackendStatus("offline");
      }
    };
    checkHealth();
    const healthInterval = setInterval(checkHealth, 15000);

    return () => {
      clearInterval(clockInterval);
      clearInterval(healthInterval);
    };
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", overflow: "hidden" }}>
      {/* Top Header */}
      <header
        style={{
          height: "48px",
          backgroundColor: "var(--bg-surface)",
          borderBottom: "1px solid var(--border-subtle)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 1.25rem",
          zIndex: 100,
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Activity size={18} style={{ color: "var(--accent-blue)" }} />
            <span style={{ fontWeight: 700, letterSpacing: "0.05em", fontSize: "0.95rem" }}>
              ALGOTRADE
            </span>
            <span style={{ fontSize: "0.65rem", color: "var(--text-muted)", border: "1px solid var(--border-strong)", padding: "0.1rem 0.35rem", borderRadius: "3px" }}>
              v1.0.0
            </span>
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.35rem",
              backgroundColor: "rgba(239, 68, 68, 0.12)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              padding: "0.2rem 0.5rem",
              borderRadius: "3px",
              color: "var(--status-red)",
              fontSize: "0.7rem",
              fontWeight: 600,
              letterSpacing: "0.04em",
            }}
          >
            <ShieldAlert size={12} />
            <span>SIMULATION ONLY — NO REAL MONEY</span>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "1.25rem", fontSize: "0.75rem" }}>
          <div className="mono" style={{ color: "var(--text-secondary)" }}>
            {currentTime}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <span
              style={{
                width: "7px",
                height: "7px",
                borderRadius: "50%",
                backgroundColor:
                  backendStatus === "online"
                    ? "var(--status-green)"
                    : backendStatus === "offline"
                    ? "var(--status-red)"
                    : "var(--status-amber)",
                display: "inline-block",
              }}
            />
            <span style={{ color: "var(--text-secondary)", textTransform: "uppercase", fontSize: "0.7rem", fontWeight: 600 }}>
              {backendStatus}
            </span>
          </div>
        </div>
      </header>

      {/* Main Shell: Sidebar + Content */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Persistent Sidebar */}
        <aside
          style={{
            width: "200px",
            backgroundColor: "var(--bg-surface)",
            borderRight: "1px solid var(--border-subtle)",
            display: "flex",
            flexDirection: "column",
            flexShrink: 0,
            overflowY: "auto",
            padding: "0.75rem 0",
          }}
        >
          <div style={{ padding: "0 0.75rem 0.5rem", fontSize: "0.65rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Workspace
          </div>

          <nav style={{ display: "flex", flexDirection: "column", gap: "0.15rem" }}>
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const isActive = currentRoute === item.route;
              return (
                <button
                  key={item.route}
                  onClick={() => onRouteChange(item.route)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.65rem",
                    padding: "0.55rem 0.85rem",
                    backgroundColor: isActive ? "var(--bg-surface-hover)" : "transparent",
                    color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
                    border: "none",
                    borderLeft: isActive ? "3px solid var(--accent-blue)" : "3px solid transparent",
                    textAlign: "left",
                    cursor: "pointer",
                    fontSize: "0.8125rem",
                    fontWeight: isActive ? 600 : 400,
                    transition: "all 0.1s ease",
                    outline: "none",
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) e.currentTarget.style.backgroundColor = "rgba(255,255,255,0.03)";
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) e.currentTarget.style.backgroundColor = "transparent";
                  }}
                >
                  <Icon size={16} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>
        </aside>

        {/* Content Viewport */}
        <main
          style={{
            flex: 1,
            overflowY: "auto",
            backgroundColor: "var(--bg-app)",
            padding: "1.5rem",
          }}
        >
          {children}
        </main>
      </div>
    </div>
  );
};
