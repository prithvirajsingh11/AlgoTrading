import React, { useState, useMemo } from "react";
import { OHLCVBar, TradeRecord } from "../types";

interface CandlestickChartProps {
  data: OHLCVBar[];
  trades?: TradeRecord[];
  height?: number;
  symbol?: string;
}

export const CandlestickChart: React.FC<CandlestickChartProps> = ({
  data,
  trades = [],
  height = 420,
  symbol = "ASSET",
}) => {
  const [showSMA10, setShowSMA10] = useState(true);
  const [showSMA20, setShowSMA20] = useState(true);
  const [showSMA50, setShowSMA50] = useState(false);
  const [showTrades, setShowTrades] = useState(true);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  // Compute SMAs
  const { sma10, sma20, sma50 } = useMemo(() => {
    const calc = (period: number) => {
      const res: (number | null)[] = [];
      let sum = 0;
      for (let i = 0; i < data.length; i++) {
        sum += data[i].close;
        if (i >= period) {
          sum -= data[i - period].close;
        }
        if (i >= period - 1) {
          res.push(sum / period);
        } else {
          res.push(null);
        }
      }
      return res;
    };
    return {
      sma10: calc(10),
      sma20: calc(20),
      sma50: calc(50),
    };
  }, [data]);

  // Dimension calculations
  const chartHeight = height - 100; // top for price, bottom 80px for volume
  const volumeHeight = 70;
  const paddingLeft = 10;
  const paddingRight = 60;
  const paddingTop = 20;

  const { minPrice, maxPrice, maxVolume } = useMemo(() => {
    if (!data.length) return { minPrice: 0, maxPrice: 1, maxVolume: 1 };
    let minP = data[0].low;
    let maxP = data[0].high;
    let maxV = data[0].volume;

    for (const b of data) {
      if (b.low < minP) minP = b.low;
      if (b.high > maxP) maxP = b.high;
      if (b.volume > maxV) maxV = b.volume;
    }
    const pad = (maxP - minP) * 0.05 || 1;
    return {
      minPrice: minP - pad,
      maxPrice: maxP + pad,
      maxVolume: maxV || 1,
    };
  }, [data]);

  if (!data || data.length === 0) {
    return (
      <div style={{ height, display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid var(--border-subtle)", borderRadius: "4px", color: "var(--text-muted)" }}>
        No historical OHLCV data available.
      </div>
    );
  }

  const svgWidth = 800; // viewBox units
  const plotWidth = svgWidth - paddingLeft - paddingRight;
  const candleWidth = Math.max(2, Math.min(14, (plotWidth / data.length) * 0.7));
  const stepX = plotWidth / (data.length > 1 ? data.length - 1 : 1);

  const getY = (price: number) => {
    const range = maxPrice - minPrice;
    if (range <= 0) return paddingTop;
    return paddingTop + (1 - (price - minPrice) / range) * chartHeight;
  };

  const getVolY = (vol: number) => {
    const h = (vol / maxVolume) * volumeHeight;
    return chartHeight + paddingTop + 30 + (volumeHeight - h);
  };

  const hoverBar = hoverIndex !== null && hoverIndex >= 0 && hoverIndex < data.length ? data[hoverIndex] : null;

  // Build path for SMA lines
  const buildSmaPath = (arr: (number | null)[]) => {
    let p = "";
    for (let i = 0; i < arr.length; i++) {
      const val = arr[i];
      if (val === null) continue;
      const x = paddingLeft + i * stepX;
      const y = getY(val);
      if (!p) p = `M ${x} ${y}`;
      else p += ` L ${x} ${y}`;
    }
    return p;
  };

  // Map trades to bar indices
  const tradeMarkers = useMemo(() => {
    if (!showTrades || !trades.length) return [];
    const markers: { x: number; y: number; type: string; price: number }[] = [];

    // Map timestamps to indices
    const dateMap = new Map<string, number>();
    data.forEach((b, idx) => {
      const d = b.timestamp.split("T")[0];
      dateMap.set(d, idx);
    });

    for (const t of trades) {
      const entryDate = t.entry_time.split("T")[0];
      const exitDate = t.exit_time.split("T")[0];

      if (dateMap.has(entryDate)) {
        const idx = dateMap.get(entryDate)!;
        markers.push({
          x: paddingLeft + idx * stepX,
          y: getY(t.entry_price),
          type: t.direction === "LONG" ? "BUY" : "SHORT",
          price: t.entry_price,
        });
      }
      if (dateMap.has(exitDate)) {
        const idx = dateMap.get(exitDate)!;
        const isStop = t.exit_reason.toLowerCase().includes("stop");
        markers.push({
          x: paddingLeft + idx * stepX,
          y: getY(t.exit_price),
          type: isStop ? "STOP" : "EXIT",
          price: t.exit_price,
        });
      }
    }
    return markers;
  }, [data, trades, showTrades, stepX, paddingLeft, minPrice, maxPrice]);

  return (
    <div style={{ backgroundColor: "var(--bg-surface)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "1rem" }}>
      {/* Chart Controls & Legend */}
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: "1rem", marginBottom: "0.75rem", borderBottom: "1px solid var(--border-subtle)", paddingBottom: "0.75rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <span style={{ fontWeight: 700, fontSize: "1rem" }} className="mono">{symbol}</span>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{data.length} Bars</span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "1rem", fontSize: "0.75rem" }}>
          <label style={{ display: "flex", alignItems: "center", gap: "0.35rem", cursor: "pointer", color: "var(--status-amber)" }}>
            <input type="checkbox" checked={showSMA10} onChange={(e) => setShowSMA10(e.target.checked)} />
            SMA 10
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: "0.35rem", cursor: "pointer", color: "var(--accent-blue)" }}>
            <input type="checkbox" checked={showSMA20} onChange={(e) => setShowSMA20(e.target.checked)} />
            SMA 20
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: "0.35rem", cursor: "pointer", color: "var(--status-purple)" }}>
            <input type="checkbox" checked={showSMA50} onChange={(e) => setShowSMA50(e.target.checked)} />
            SMA 50
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: "0.35rem", cursor: "pointer", color: "var(--text-secondary)" }}>
            <input type="checkbox" checked={showTrades} onChange={(e) => setShowTrades(e.target.checked)} />
            Trade Markers ({tradeMarkers.length})
          </label>
        </div>
      </div>

      {/* Hover Inspection HUD */}
      <div style={{ height: "24px", fontSize: "0.75rem", display: "flex", alignItems: "center", gap: "1rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }} className="mono">
        {hoverBar ? (
          <>
            <span>Date: <strong style={{ color: "var(--text-primary)" }}>{hoverBar.timestamp.split("T")[0]}</strong></span>
            <span>O: <strong style={{ color: "var(--text-primary)" }}>${hoverBar.open.toFixed(2)}</strong></span>
            <span>H: <strong style={{ color: "var(--text-primary)" }}>${hoverBar.high.toFixed(2)}</strong></span>
            <span>L: <strong style={{ color: "var(--text-primary)" }}>${hoverBar.low.toFixed(2)}</strong></span>
            <span>C: <strong style={{ color: hoverBar.close >= hoverBar.open ? "var(--status-green)" : "var(--status-red)" }}>${hoverBar.close.toFixed(2)}</strong></span>
            <span>Vol: <strong style={{ color: "var(--text-primary)" }}>{hoverBar.volume.toLocaleString()}</strong></span>
          </>
        ) : (
          <span style={{ color: "var(--text-muted)" }}>Hover over chart to inspect bar prices</span>
        )}
      </div>

      {/* SVG Canvas */}
      <svg
        viewBox={`0 0 ${svgWidth} ${height}`}
        style={{ width: "100%", height: "auto", display: "block", overflow: "visible" }}
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const mouseX = ((e.clientX - rect.left) / rect.width) * svgWidth - paddingLeft;
          const idx = Math.round(mouseX / stepX);
          if (idx >= 0 && idx < data.length) {
            setHoverIndex(idx);
          }
        }}
        onMouseLeave={() => setHoverIndex(null)}
      >
        {/* Horizontal Price Grid Lines */}
        {[0, 0.25, 0.5, 0.75, 1].map((pct, i) => {
          const p = minPrice + pct * (maxPrice - minPrice);
          const y = getY(p);
          return (
            <g key={i}>
              <line x1={paddingLeft} y1={y} x2={svgWidth - paddingRight} y2={y} stroke="var(--border-subtle)" strokeDasharray="3 3" />
              <text x={svgWidth - paddingRight + 6} y={y + 3} fill="var(--text-muted)" fontSize="9" className="mono">
                ${p.toFixed(2)}
              </text>
            </g>
          );
        })}

        {/* Volume Separator */}
        <line x1={paddingLeft} y1={chartHeight + paddingTop + 20} x2={svgWidth - paddingRight} y2={chartHeight + paddingTop + 20} stroke="var(--border-strong)" />

        {/* Volume Bars */}
        {data.map((b, i) => {
          const x = paddingLeft + i * stepX;
          const y = getVolY(b.volume);
          const h = chartHeight + paddingTop + 30 + volumeHeight - y;
          const isGreen = b.close >= b.open;
          return (
            <rect
              key={`vol-${i}`}
              x={x - candleWidth / 2}
              y={y}
              width={candleWidth}
              height={Math.max(1, h)}
              fill={isGreen ? "rgba(16, 185, 129, 0.25)" : "rgba(239, 68, 68, 0.25)"}
            />
          );
        })}

        {/* Candlesticks */}
        {data.map((b, i) => {
          const x = paddingLeft + i * stepX;
          const isGreen = b.close >= b.open;
          const color = isGreen ? "var(--status-green)" : "var(--status-red)";
          const highY = getY(b.high);
          const lowY = getY(b.low);
          const openY = getY(b.open);
          const closeY = getY(b.close);
          const bodyY = Math.min(openY, closeY);
          const bodyH = Math.max(1.5, Math.abs(openY - closeY));

          return (
            <g key={`candle-${i}`}>
              {/* Wick */}
              <line x1={x} y1={highY} x2={x} y2={lowY} stroke={color} strokeWidth="1.2" />
              {/* Body */}
              <rect
                x={x - candleWidth / 2}
                y={bodyY}
                width={candleWidth}
                height={bodyH}
                fill={color}
              />
            </g>
          );
        })}

        {/* SMA Lines */}
        {showSMA10 && <path d={buildSmaPath(sma10)} fill="none" stroke="var(--status-amber)" strokeWidth="1.5" />}
        {showSMA20 && <path d={buildSmaPath(sma20)} fill="none" stroke="var(--accent-blue)" strokeWidth="1.5" />}
        {showSMA50 && <path d={buildSmaPath(sma50)} fill="none" stroke="var(--status-purple)" strokeWidth="1.5" />}

        {/* Trade Markers */}
        {tradeMarkers.map((m, idx) => {
          if (m.type === "BUY") {
            return (
              <polygon
                key={`m-${idx}`}
                points={`${m.x},${m.y + 8} ${m.x - 5},${m.y + 16} ${m.x + 5},${m.y + 16}`}
                fill="var(--status-green)"
                stroke="#000"
                strokeWidth="1"
              />
            );
          } else if (m.type === "SHORT" || m.type === "EXIT") {
            return (
              <polygon
                key={`m-${idx}`}
                points={`${m.x},${m.y - 8} ${m.x - 5},${m.y - 16} ${m.x + 5},${m.y - 16}`}
                fill="var(--status-red)"
                stroke="#000"
                strokeWidth="1"
              />
            );
          } else if (m.type === "STOP") {
            return (
              <g key={`m-${idx}`} stroke="var(--status-red)" strokeWidth="2">
                <line x1={m.x - 5} y1={m.y - 5} x2={m.x + 5} y2={m.y + 5} />
                <line x1={m.x - 5} y1={m.y + 5} x2={m.x + 5} y2={m.y - 5} />
              </g>
            );
          }
          return null;
        })}

        {/* Hover Crosshair */}
        {hoverIndex !== null && (
          <line
            x1={paddingLeft + hoverIndex * stepX}
            y1={paddingTop}
            x2={paddingLeft + hoverIndex * stepX}
            y2={height - 20}
            stroke="var(--text-secondary)"
            strokeWidth="1"
            strokeDasharray="2 2"
          />
        )}
      </svg>
    </div>
  );
};
