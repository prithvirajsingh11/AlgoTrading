import React, { useState, useEffect, Suspense, lazy } from "react";
import { Layout, NavRoute } from "./components/Layout";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { LoadingSpinner } from "./components/Common";

// Code splitting via React.lazy with dynamic imports
const DashboardPage = lazy(() => import("./pages/DashboardPage").then((m) => ({ default: m.DashboardPage })));
const BacktestPage = lazy(() => import("./pages/BacktestPage").then((m) => ({ default: m.BacktestPage })));
const StrategyLabPage = lazy(() => import("./pages/StrategyLabPage").then((m) => ({ default: m.StrategyLabPage })));
const ExperimentsPage = lazy(() => import("./pages/ExperimentsPage").then((m) => ({ default: m.ExperimentsPage })));
const DatasetPage = lazy(() => import("./pages/DatasetPage").then((m) => ({ default: m.DatasetPage })));
const MLLabPage = lazy(() => import("./pages/MLLabPage").then((m) => ({ default: m.MLLabPage })));
const JevLabPage = lazy(() => import("./pages/JevLabPage").then((m) => ({ default: m.JevLabPage })));
const ComparisonPage = lazy(() => import("./pages/ComparisonPage").then((m) => ({ default: m.ComparisonPage })));
const PortfolioPage = lazy(() => import("./pages/PortfolioPage").then((m) => ({ default: m.PortfolioPage })));
const PaperTradingPage = lazy(() => import("./pages/PaperTradingPage").then((m) => ({ default: m.PaperTradingPage })));
const SettingsPage = lazy(() => import("./pages/SettingsPage").then((m) => ({ default: m.SettingsPage })));

export const App: React.FC = () => {
  // Sync state with URL hash
  const getRouteFromHash = (): NavRoute => {
    const hash = window.location.hash.replace(/^#\/?/, "").toLowerCase();
    const validRoutes: NavRoute[] = [
      "dashboard",
      "backtests",
      "strategies",
      "experiments",
      "datasets",
      "ml-lab",
      "jev-lab",
      "comparison",
      "portfolio",
      "paper-trade",
      "settings",
    ];
    if (validRoutes.includes(hash as NavRoute)) {
      return hash as NavRoute;
    }
    return "dashboard";
  };

  const [currentRoute, setCurrentRoute] = useState<NavRoute>(getRouteFromHash());

  useEffect(() => {
    const onHashChange = () => {
      setCurrentRoute(getRouteFromHash());
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const handleRouteChange = (route: NavRoute) => {
    window.location.hash = `#${route}`;
    setCurrentRoute(route);
  };

  const renderCurrentPage = () => {
    switch (currentRoute) {
      case "dashboard":
        return <DashboardPage onNavigate={(r) => handleRouteChange(r as NavRoute)} />;
      case "backtests":
        return <BacktestPage />;
      case "strategies":
        return <StrategyLabPage />;
      case "experiments":
        return <ExperimentsPage />;
      case "datasets":
        return <DatasetPage />;
      case "ml-lab":
        return <MLLabPage />;
      case "jev-lab":
        return <JevLabPage />;
      case "comparison":
        return <ComparisonPage />;
      case "portfolio":
        return <PortfolioPage />;
      case "paper-trade":
        return <PaperTradingPage />;
      case "settings":
        return <SettingsPage />;
      default:
        return <DashboardPage onNavigate={(r) => handleRouteChange(r as NavRoute)} />;
    }
  };

  return (
    <Layout currentRoute={currentRoute} onRouteChange={handleRouteChange}>
      <ErrorBoundary>
        <Suspense
          fallback={
            <div className="flex justify-center items-center min-h-[400px]">
              <LoadingSpinner message="Loading institutional module..." />
            </div>
          }
        >
          {renderCurrentPage()}
        </Suspense>
      </ErrorBoundary>
    </Layout>
  );
};

export default App;
