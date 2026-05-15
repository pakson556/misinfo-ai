import React, { useEffect, useState } from "react";
import MetricsCard from "./MetricsCard.jsx";
import RiskTrendChart from "./RiskTrendChart.jsx";
import BreakdownBars from "./BreakdownBars.jsx";
import RecentAnalyses from "./RecentAnalyses.jsx";
import { api } from "../../services/api.js";

const POLL_MS = 30_000;

const TIME_RANGES = [
  { label: "24h", value: "24h", window: 2000, bucket: 3600 },
  { label: "7d", value: "7d", window: 10000, bucket: 86400 },
  { label: "30d", value: "30d", window: 50000, bucket: 86400 },
];

function formatLatency(ms) {
  if (ms == null) return "—";
  const n = Number(ms);
  if (!Number.isFinite(n)) return "—";

  if (n < 1000) return `${Math.round(n)}ms`;
  if (n < 60_000) return `${(n / 1000).toFixed(1)}s`;

  const minutes = Math.floor(n / 60_000);
  const seconds = Math.round((n % 60_000) / 1000);
  return `${minutes}m ${seconds}s`;
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState("24h");
  const [exporting, setExporting] = useState(false);

  async function load() {
    try {
      setErr("");
      const range =
        TIME_RANGES.find((r) => r.value === timeRange) || TIME_RANGES[0];

      const res = await api.getDashboardMetrics(range.window, 10, range.bucket);

      setData(res);
    } catch (e) {
      setErr(String(e?.message || e));
    } finally {
      setLoading(false);
    }
  }

  function exportData() {
    if (!data) return;

    setExporting(true);
    try {
      const dataStr = JSON.stringify(data, null, 2);
      const blob = new Blob([dataStr], { type: "application/json" });
      const url = URL.createObjectURL(blob);

      const a = document.createElement("a");
      a.href = url;
      a.download = `dashboard-export-${new Date().toISOString().split("T")[0]}.json`;
      a.click();

      URL.revokeObjectURL(url);
    } catch (e) {
      console.error("Export failed:", e);
    } finally {
      setExporting(false);
    }
  }

  useEffect(() => {
    load();
    const id = setInterval(load, POLL_MS);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeRange]);

  if (loading) {
    return (
      <div className="p-6">
        <div className="text-xl font-semibold text-gray-900">Performance Dashboard</div>
        <div className="mt-2 text-sm text-gray-500">Loading metrics…</div>
      </div>
    );
  }

  const totals = data?.totals || {};
  const bands = data?.bands || {};
  const verdicts = data?.verdicts || {};
  const stance = data?.stance || {};
  const latency = data?.latency_ms || {};
  const risk = data?.risk || {};
  const conf = data?.confidence || {};

  const analyses = totals.analyses || 0;
  const avgRiskPct = risk.avg == null ? "—" : `${Math.round(risk.avg * 100)}%`;
  const avgConfPct = conf.avg == null ? "—" : `${Math.round(conf.avg * 100)}%`;

  const p95Formatted = formatLatency(latency.p95);
  const p95Subtext =
    latency.p95 == null
      ? "Enable latency tracking"
      : Number(latency.p95) > 1000
        ? "95th percentile (slow response times)"
        : "95th percentile response time";

  return (
    <div className="p-6">
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-2xl font-semibold text-gray-900">Performance Dashboard</div>
            <div className="text-sm text-gray-500">
              Live operational metrics from{" "}
              <span className="font-mono text-xs">
                {data?.events_log ? data.events_log.split("/").pop() : "events.jsonl"}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className="px-3 py-1.5 text-sm bg-white border border-gray-300 rounded-lg text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {TIME_RANGES.map((range) => (
                <option key={range.value} value={range.value}>
                  {range.label}
                </option>
              ))}
            </select>

            <button
              onClick={exportData}
              disabled={exporting || !data}
              className="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50"
            >
              {exporting ? "Exporting…" : "Export Data"}
            </button>
          </div>
        </div>

        {err ? (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {err}
          </div>
        ) : null}
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <MetricsCard title="Total analyses" value={analyses} sub="Count of predict events" />
        <MetricsCard title="Avg risk" value={avgRiskPct} sub="Mean misinfo_probability" />
        <MetricsCard title="Avg confidence" value={avgConfPct} sub="Mean confidence" />
        <MetricsCard title="Latency p95" value={p95Formatted} sub={p95Subtext} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <RiskTrendChart timeseries={data?.timeseries || []} />
        </div>
        <BreakdownBars title="Risk bands" items={bands} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <BreakdownBars title="Action verdicts" items={verdicts} />
        <BreakdownBars title="Stance distribution" items={stance} />
      </div>

      <div className="mt-4">
        <RecentAnalyses rows={data?.recent || []} />
      </div>

      {data?.generated_at ? (
        <div className="mt-4 text-xs text-gray-400 text-right">
          Last updated: {new Date(data.generated_at * 1000).toLocaleString()}
        </div>
      ) : null}
    </div>
  );
}