import React, { useState } from "react";

const SEVERITY_STYLES = {
  high:   "bg-red-900 border-red-500 text-red-100",
  medium: "bg-yellow-900 border-yellow-500 text-yellow-100",
  low:    "bg-blue-900 border-blue-500 text-blue-100",
};

const BEHAVIOR_ICONS = {
  loitering:      "🕐",
  repeated_path:  "🔄",
  sudden_motion:  "⚡",
};

/**
 * AlertsPanel – scrollable real-time alert feed.
 */
export default function AlertsPanel({ alerts, onAcknowledge }) {
  const [filter, setFilter] = useState("all");

  const filtered = filter === "all"
    ? alerts
    : alerts.filter((a) => a.severity === filter);

  const unackCount = alerts.filter((a) => !a.acknowledged).length;

  return (
    <div className="bg-slate-800 rounded-xl shadow-lg flex flex-col h-full max-h-screen">
      {/* Header */}
      <div className="px-4 py-3 bg-slate-700 rounded-t-xl flex items-center justify-between shrink-0">
        <h2 className="font-semibold text-slate-200">
          🚨 Alerts
          {unackCount > 0 && (
            <span className="ml-2 text-xs bg-red-600 text-white px-2 py-0.5 rounded-full">
              {unackCount} new
            </span>
          )}
        </h2>
        <div className="flex gap-1">
          {["all", "high", "medium", "low"].map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`text-xs px-2 py-1 rounded transition ${
                filter === s
                  ? "bg-blue-600 text-white"
                  : "bg-slate-600 text-slate-300 hover:bg-slate-500"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {filtered.length === 0 && (
          <p className="text-slate-500 text-sm text-center mt-8">
            No alerts yet. System is monitoring…
          </p>
        )}
        {filtered.map((alert, idx) => (
          <div
            key={idx}
            className={`border rounded-lg p-3 text-sm ${
              SEVERITY_STYLES[alert.severity] ?? "bg-slate-700 border-slate-600"
            } ${alert.acknowledged ? "opacity-50" : ""}`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-base">
                    {BEHAVIOR_ICONS[alert.behavior_type] ?? "⚠"}
                  </span>
                  <span className="font-semibold uppercase text-xs tracking-wide">
                    {alert.behavior_type?.replace("_", " ")}
                  </span>
                  <span className="text-xs opacity-70 uppercase">
                    ID:{alert.track_id}
                  </span>
                </div>
                <p className="text-xs leading-relaxed opacity-90">{alert.message}</p>
                <p className="text-xs opacity-50 mt-1">
                  {new Date(alert.timestamp * 1000).toLocaleTimeString()}
                </p>
              </div>
              {!alert.acknowledged && (
                <button
                  onClick={() => onAcknowledge(idx)}
                  className="text-xs shrink-0 bg-white/10 hover:bg-white/20 px-2 py-1 rounded transition"
                >
                  ACK
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
