import React from "react";

function timeAgo(epochSeconds) {
  if (!epochSeconds) return "";
  const diff = Math.max(0, Math.floor(Date.now() / 1000 - epochSeconds));
  const m = Math.floor(diff / 60);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

export default function RecentAnalyses({ rows }) {
  // Sort rows by timestamp (newest first)
  const sortedRows = [...(rows || [])].sort((a, b) => {
    // Handle null timestamps (put them at the end)
    if (!a.ts) return 1;
    if (!b.ts) return -1;
    return b.ts - a.ts; // descending (newest first)
  });

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="mb-3 text-sm font-semibold text-gray-900">Recent analyses</div>

      <div className="space-y-3">
        {sortedRows.map((r, idx) => (
          <div key={r.request_id || idx} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
            <div className="flex items-center justify-between">
              <div className="text-xs text-gray-500">{timeAgo(r.ts)}</div>
              <div className="text-xs text-gray-600">
                {r.risk_band || "—"} • {r.verdict || "—"}
              </div>
            </div>

            <div className="mt-2 text-sm text-gray-900">
              {r.text_preview || "(no preview)"}
            </div>

            <div className="mt-2 text-xs text-gray-500">
              risk: {r.misinfo_probability != null ? `${Math.round(r.misinfo_probability * 100)}%` : "—"} •{" "}
              conf: {r.confidence != null ? `${Math.round(r.confidence * 100)}%` : "—"} •{" "}
              stance: {r.stance || "—"}
            </div>
          </div>
        ))}

        {(!rows || rows.length === 0) ? (
          <div className="text-xs text-gray-500">No recent events found yet. Run a few predictions.</div>
        ) : null}
      </div>
    </div>
  );
}