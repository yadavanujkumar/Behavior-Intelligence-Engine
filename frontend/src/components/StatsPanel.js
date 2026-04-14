import React from "react";

/**
 * StatsPanel – top-level KPI cards.
 */
export default function StatsPanel({ stats }) {
  const cards = [
    { label: "Active Tracks", value: stats.active_tracks ?? 0, icon: "👤", color: "text-blue-400" },
    { label: "Total Alerts", value: stats.total_alerts ?? 0, icon: "🚨", color: "text-red-400" },
    { label: "Uptime", value: formatUptime(stats.uptime_seconds), icon: "⏱", color: "text-green-400" },
    { label: "FPS", value: `${stats.fps ?? 0}`, icon: "🎞", color: "text-yellow-400" },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {cards.map((c) => (
        <div key={c.label} className="bg-slate-800 rounded-xl p-4 shadow">
          <div className="text-2xl mb-1">{c.icon}</div>
          <div className={`text-2xl font-bold ${c.color}`}>{c.value}</div>
          <div className="text-xs text-slate-400 mt-1">{c.label}</div>
        </div>
      ))}
    </div>
  );
}

function formatUptime(seconds) {
  if (!seconds) return "0s";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m ${s}s` : `${s}s`;
}
