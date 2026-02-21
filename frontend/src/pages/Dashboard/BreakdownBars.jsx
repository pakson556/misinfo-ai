import React from "react";

function Row({ label, value, total }) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div className="mb-3">
      <div className="flex items-center justify-between text-xs text-gray-600">
        <span>{label}</span>
        <span>
          {value} ({pct}%)
        </span>
      </div>
      <div className="mt-1 h-2 w-full rounded-full bg-gray-100">
        <div className="h-2 rounded-full bg-blue-500" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function BreakdownBars({ title, items }) {
  const total = Object.values(items || {}).reduce((a, b) => a + (b || 0), 0);

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="mb-3 text-sm font-semibold text-gray-900">{title}</div>
      {Object.entries(items || {}).map(([k, v]) => (
        <Row key={k} label={k} value={v || 0} total={total} />
      ))}
      {total === 0 ? (
        <div className="text-xs text-gray-400">No events yet. Run a prediction.</div>
      ) : null}
    </div>
  );
}
