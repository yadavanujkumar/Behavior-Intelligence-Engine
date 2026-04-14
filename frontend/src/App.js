import React, { useState, useEffect, useCallback } from "react";
import VideoFeed from "./components/VideoFeed";
import AlertsPanel from "./components/AlertsPanel";
import StatsPanel from "./components/StatsPanel";
import BehaviorChart from "./components/BehaviorChart";
import axios from "axios";

const API_BASE = process.env.REACT_APP_API_URL || "";

export default function App() {
  const [alerts, setAlerts] = useState([]);
  const [stats, setStats] = useState(null);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [connected, setConnected] = useState(false);

  // Poll /alerts and /stats every 2 seconds
  const fetchData = useCallback(async () => {
    try {
      const [alertsRes, statsRes] = await Promise.all([
        axios.get(`${API_BASE}/alerts?limit=50`),
        axios.get(`${API_BASE}/stats`),
      ]);
      setAlerts(alertsRes.data);
      setStats(statsRes.data);
      setConnected(true);
    } catch {
      setConnected(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 2000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const acknowledgeAlert = async (index) => {
    try {
      await axios.patch(`${API_BASE}/alerts/${index}/ack`, { acknowledged: true });
      fetchData();
    } catch (e) {
      console.error("Acknowledge failed", e);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-4">
      {/* Header */}
      <header className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-red-500 animate-pulse" />
          <h1 className="text-2xl font-bold tracking-wide text-blue-400">
            🔍 Behavior Intelligence Engine
          </h1>
        </div>
        <div className="flex items-center gap-4">
          <span
            className={`text-sm px-3 py-1 rounded-full ${
              connected ? "bg-green-800 text-green-200" : "bg-red-800 text-red-200"
            }`}
          >
            {connected ? "● Connected" : "○ Disconnected"}
          </span>
          <button
            onClick={() => setShowHeatmap((h) => !h)}
            className="px-4 py-1.5 bg-blue-700 hover:bg-blue-600 rounded text-sm font-medium transition"
          >
            {showHeatmap ? "Normal View" : "Heatmap View"}
          </button>
        </div>
      </header>

      {/* Main grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Left – Video + Stats */}
        <div className="xl:col-span-2 flex flex-col gap-4">
          <VideoFeed apiBase={API_BASE} showHeatmap={showHeatmap} />
          {stats && <StatsPanel stats={stats} />}
          {stats && <BehaviorChart stats={stats} />}
        </div>

        {/* Right – Alerts */}
        <div>
          <AlertsPanel alerts={alerts} onAcknowledge={acknowledgeAlert} />
        </div>
      </div>
    </div>
  );
}
