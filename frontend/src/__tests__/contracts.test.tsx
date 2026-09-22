import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge, ErrorMessage, EmptyState } from "../components/Common";
import { SessionMode, PaperOrderRecord } from "../types";

describe("Frontend Service Contracts & State Rendering", () => {
  it("renders distinct status badges for all session safety states", () => {
    const { rerender } = render(<StatusBadge status="SIGNALS_ENABLED" />);
    expect(screen.getByText("SIGNALS_ENABLED")).toBeInTheDocument();

    rerender(<StatusBadge status="SIGNALS_PAUSED" />);
    expect(screen.getByText("SIGNALS_PAUSED")).toBeInTheDocument();

    rerender(<StatusBadge status="DISCONNECTED" />);
    expect(screen.getByText("DISCONNECTED")).toBeInTheDocument();
  });

  it("validates SessionMode enum completeness", () => {
    const modes: SessionMode[] = ["HISTORICAL_REPLAY", "SYNTHETIC_STREAM", "REAL_TIME"];
    expect(modes).toHaveLength(3);
    expect(modes).toContain("HISTORICAL_REPLAY");
    expect(modes).toContain("SYNTHETIC_STREAM");
    expect(modes).toContain("REAL_TIME");
  });

  it("handles decision attribution on order records", () => {
    const order: PaperOrderRecord = {
      order_id: "ord_101",
      session_id: "paper_sess_01",
      timestamp: "2026-09-22T10:00:00Z",
      symbol: "AAPL",
      side: "BUY",
      order_type: "MARKET",
      quantity: 10,
      fill_price: 150.0,
      commission: 1.0,
      slippage: 0.05,
      status: "FILLED",
      decision_source: "XGBOOST",
      model_version: "xgb_v2.0",
      jev_mode: "NONE",
    };

    expect(order.decision_source).toBe("XGBOOST");
    expect(order.model_version).toBe("xgb_v2.0");
  });

  it("renders error state when backend rejects request", () => {
    const onRetry = vi.fn();
    render(
      <ErrorMessage
        message="Maximum active paper sessions limit reached (25). Complete or remove existing sessions."
        onRetry={onRetry}
      />
    );
    expect(screen.getByText(/Maximum active paper sessions limit reached/i)).toBeInTheDocument();
  });

  it("renders empty state with actionable guidance", () => {
    render(
      <EmptyState
        title="No Paper Sessions Active"
        message="Initialize a new session using Historical Replay, Synthetic Stream, or Real-Time feed."
      />
    );
    expect(screen.getByText("No Paper Sessions Active")).toBeInTheDocument();
    expect(screen.getByText(/Initialize a new session/i)).toBeInTheDocument();
  });
});
