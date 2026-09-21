import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge, LoadingSpinner, ErrorMessage, EmptyState } from "../components/Common";
import { Layout } from "../components/Layout";

describe("AlgoTrade Common Components", () => {
  it("renders LoadingSpinner with custom message", () => {
    render(<LoadingSpinner message="Calculating Sharpe ratio..." />);
    expect(screen.getByText("Calculating Sharpe ratio...")).toBeInTheDocument();
  });

  it("renders ErrorMessage with retry button", () => {
    const onRetry = vi.fn();
    render(<ErrorMessage message="Dataset fetch failed" onRetry={onRetry} />);
    expect(screen.getByText("Dataset fetch failed")).toBeInTheDocument();
    expect(screen.getByText("Retry Request")).toBeInTheDocument();
  });

  it("renders StatusBadge with appropriate color variant", () => {
    const { container } = render(<StatusBadge status="ACTIVE" />);
    expect(container.querySelector(".badge-green")).toBeInTheDocument();
    expect(screen.getByText("ACTIVE")).toBeInTheDocument();
  });

  it("renders EmptyState with title and message", () => {
    render(<EmptyState title="No Trades" message="No trades executed." />);
    expect(screen.getByText("No Trades")).toBeInTheDocument();
    expect(screen.getByText("No trades executed.")).toBeInTheDocument();
  });
});

describe("AlgoTrade Application Layout Shell", () => {
  it("renders persistent header and simulation disclaimer", () => {
    render(
      <Layout currentRoute="dashboard" onRouteChange={() => {}}>
        <div>Dashboard Content</div>
      </Layout>
    );

    expect(screen.getByText("ALGOTRADE")).toBeInTheDocument();
    expect(screen.getByText("SIMULATION ONLY — NO REAL MONEY")).toBeInTheDocument();
    expect(screen.getByText("Dashboard Content")).toBeInTheDocument();
  });

  it("renders all core navigation links in sidebar", () => {
    render(
      <Layout currentRoute="dashboard" onRouteChange={() => {}}>
        <div />
      </Layout>
    );

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Backtests")).toBeInTheDocument();
    expect(screen.getByText("Strategies")).toBeInTheDocument();
    expect(screen.getByText("Experiments")).toBeInTheDocument();
    expect(screen.getByText("Datasets")).toBeInTheDocument();
    expect(screen.getByText("ML Lab")).toBeInTheDocument();
    expect(screen.getByText("Jev Lab")).toBeInTheDocument();
    expect(screen.getByText("Comparison")).toBeInTheDocument();
    expect(screen.getByText("Portfolio")).toBeInTheDocument();
    expect(screen.getByText("Paper Trade")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });
});
