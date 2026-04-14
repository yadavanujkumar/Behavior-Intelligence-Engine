import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";

const BEHAVIOR_COLORS = {
  loitering: "#f59e0b",
  repeated_path: "#3b82f6",
  sudden_motion: "#ef4444",
};

const SEVERITY_COLORS = {
  high: "#ef4444",
  medium: "#f59e0b",
  low: "#3b82f6",
};

/**
 * BehaviorChart – bar + pie charts visualising alert distributions.
 */
export default function BehaviorChart({ stats }) {
  const byType = Object.entries(stats.alerts_by_type ?? {}).map(([name, value]) => ({
    name: name.replace("_", " "),
    value,
    fill: BEHAVIOR_COLORS[name] ?? "#64748b",
  }));

  const bySeverity = Object.entries(stats.alerts_by_severity ?? {}).map(
    ([name, value]) => ({ name, value })
  );

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* By behavior type */}
      <div className="bg-slate-800 rounded-xl p-4 shadow">
        <h3 className="text-sm font-semibold text-slate-300 mb-3">Alerts by Behavior</h3>
        {byType.length === 0 ? (
          <p className="text-slate-500 text-sm text-center py-6">No data yet</p>
        ) : (
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={byType}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} />
              <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} />
              <Tooltip
                contentStyle={{ backgroundColor: "#1e293b", border: "none" }}
                labelStyle={{ color: "#f1f5f9" }}
              />
              <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                {byType.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* By severity */}
      <div className="bg-slate-800 rounded-xl p-4 shadow">
        <h3 className="text-sm font-semibold text-slate-300 mb-3">Alerts by Severity</h3>
        {bySeverity.length === 0 ? (
          <p className="text-slate-500 text-sm text-center py-6">No data yet</p>
        ) : (
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie
                data={bySeverity}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={65}
                label={({ name, value }) => `${name}: ${value}`}
                labelLine={false}
              >
                {bySeverity.map((entry, i) => (
                  <Cell
                    key={i}
                    fill={SEVERITY_COLORS[entry.name] ?? "#64748b"}
                  />
                ))}
              </Pie>
              <Legend
                formatter={(value) => (
                  <span style={{ color: "#94a3b8", fontSize: 12 }}>{value}</span>
                )}
              />
              <Tooltip
                contentStyle={{ backgroundColor: "#1e293b", border: "none" }}
              />
            </PieChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
