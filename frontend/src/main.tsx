import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import "./index.css";
import { RefreshContext } from "./lib/hooks";
import Dashboard from "./pages/Dashboard";
import { Analytics, PerformanceOverview, Trades } from "./pages/Performance";
import ScanHistory from "./pages/Scans";
import { LiveSignals, SignalHistory } from "./pages/Signals";
import Strategy from "./pages/Strategy";
import { DataHealth, Settings } from "./pages/System";

export function App() {
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [tick, setTick] = useState(0);
  return (
    <RefreshContext.Provider value={{ autoRefresh, setAutoRefresh, tick, bump: () => setTick((t) => t + 1) }}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="signals/live" element={<LiveSignals />} />
          <Route path="signals/history" element={<SignalHistory />} />
          <Route path="scans" element={<ScanHistory />} />
          <Route path="performance" element={<PerformanceOverview />} />
          <Route path="performance/trades" element={<Trades />} />
          <Route path="performance/analytics" element={<Analytics />} />
          <Route path="strategy" element={<Strategy />} />
          <Route path="data-health" element={<DataHealth />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<Dashboard />} />
        </Route>
      </Routes>
    </RefreshContext.Provider>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
