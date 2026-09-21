import React from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
} from "recharts";
import { EquityPoint, DrawdownPoint } from "../types";

interface EquityDrawdownChartProps {
  equityCurve: EquityPoint[];
  drawdownCurve?: DrawdownPoint[];
  initialCapital?: number;
  height?: number;
}

export const EquityDrawdownChart: React.FC<EquityDrawdownChartProps> = ({
  equityCurve,
  drawdownCurve = [],
  initialCapital = 100000,
  height = 320,
}) => {
  if (!equityCurve || equityCurve.length === 0) {
    return (
      <div style={{ height, display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid var(--border-subtle)", borderRadius: "4px", color: "var(--text-muted)" }}>
        No equity curve data available.
      </div>
    );
  }

  // Format data points for charts
  const chartData = equityCurve.map((pt, idx) => {
    const ts = pt.timestamp ? pt.timestamp.split("T")[0] : `T${idx}`;
    const eq = pt.total_equity ?? pt.equity ?? initialCapital;
    const dd = drawdownCurve[idx] ? drawdownCurve[idx].drawdown_pct * 100 : (pt.drawdown_pct ? pt.drawdown_pct * 100 : 0);
    return {
      date: ts,
      equity: Math.round(eq * 100) / 100,
      drawdown: Math.round(dd * 100) / 100,
    };
  });

  const finalEquity = chartData[chartData.length - 1]?.equity ?? initialCapital;
  const isProfitable = finalEquity >= initialCapital;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      {/* Top: Equity Curve */}
      <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
          <div style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--text-secondary)" }}>
            PORTFOLIO EQUITY CURVE
          </div>
          <div className="mono" style={{ fontSize: "0.875rem", fontWeight: 700, color: isProfitable ? "var(--status-green)" : "var(--status-red)" }}>
            Current: ${finalEquity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>

        <div style={{ width: "100%", height: height - 100 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
              <defs>
                <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={isProfitable ? "#10B981" : "#EF4444"} stopOpacity={0.2} />
                  <stop offset="95%" stopColor={isProfitable ? "#10B981" : "#EF4444"} stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" stroke="var(--text-muted)" fontSize={10} tickLine={false} />
              <YAxis
                domain={["auto", "auto"]}
                stroke="var(--text-muted)"
                fontSize={10}
                tickLine={false}
                tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
              />
              <Tooltip
                contentStyle={{ backgroundColor: "var(--bg-surface-elevated)", borderColor: "var(--border-strong)", borderRadius: "4px", fontSize: "0.75rem" }}
                formatter={(val: number) => [`$${val.toLocaleString()}`, "Equity"]}
              />
              <ReferenceLine y={initialCapital} stroke="var(--text-muted)" strokeDasharray="3 3" label={{ value: "Initial Capital", fill: "var(--text-muted)", fontSize: 9 }} />
              <Area type="monotone" dataKey="equity" stroke={isProfitable ? "#10B981" : "#EF4444"} strokeWidth={1.8} fill="url(#equityGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Bottom: Underwater Drawdown Curve */}
      <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1rem" }}>
        <div style={{ fontSize: "0.8125rem", fontWeight: 600, color: "var(--text-secondary)", marginBottom: "0.5rem" }}>
          UNDERWATER DRAWDOWN (%)
        </div>
        <div style={{ width: "100%", height: 100 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 0 }}>
              <defs>
                <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#EF4444" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#EF4444" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" stroke="var(--text-muted)" fontSize={9} tickLine={false} hide />
              <YAxis
                reversed
                domain={[0, "dataMax + 2"]}
                stroke="var(--text-muted)"
                fontSize={9}
                tickLine={false}
                tickFormatter={(v) => `-${v.toFixed(0)}%`}
              />
              <Tooltip
                contentStyle={{ backgroundColor: "var(--bg-surface-elevated)", borderColor: "var(--border-strong)", borderRadius: "4px", fontSize: "0.75rem" }}
                formatter={(val: number) => [`-${val}%`, "Drawdown"]}
              />
              <Area type="monotone" dataKey="drawdown" stroke="#EF4444" strokeWidth={1.2} fill="url(#ddGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
