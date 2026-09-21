import React, { useState, useEffect } from "react";
import { Layout, NavRoute } from "./components/Layout";
import { DashboardPage } from "./pages/DashboardPage";
import { BacktestPage } from "./pages/BacktestPage";
import { StrategyLabPage } from "./pages/StrategyLabPage";
import { ExperimentsPage } from "./pages/ExperimentsPage";
import { DatasetPage } from "./pages/DatasetPage";
import { MLLabPage } from "./pages/MLLabPage";
import { JevLabPage } from "./pages/JevLabPage";
import { ComparisonPage } from "./pages/ComparisonPage";
import { PortfolioPage } from "./pages/PortfolioPage";
import { PaperTradingPage } from "./pages/PaperTradingPage";
import { SettingsPage } from "./pages/SettingsPage";

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
      {renderCurrentPage()}
    </Layout>
  );
};

export default App;
