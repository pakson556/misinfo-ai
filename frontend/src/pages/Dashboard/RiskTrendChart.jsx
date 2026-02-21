import React, { useMemo } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

function fmtTick(epochSeconds, { showDate = false, useUTC = false } = {}) {
  try {
    const d = new Date(epochSeconds * 1000);
    const opts = showDate
      ? { weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false }
      : { hour: "2-digit", minute: "2-digit", hour12: false };

    if (useUTC) opts.timeZone = "UTC";
    return d.toLocaleString([], opts);
  } catch {
    return "";
  }
}

function fmtTooltip(epochSeconds, { useUTC = false } = {}) {
  try {
    const d = new Date(epochSeconds * 1000);
    const opts = {
      weekday: "short",
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    };
    if (useUTC) opts.timeZone = "UTC";
    return d.toLocaleString([], opts);
  } catch {
    return "";
  }
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;

  const p = payload[0]?.payload || {};
  const risk = p.avg_risk_pct ?? null;
  const count = Number(p.count ?? 0);

  return (
    <div className="bg-white p-3 border border-gray-200 rounded-lg shadow-lg">
      <p className="text-xs font-medium text-gray-900">
        {fmtTooltip(label, { useUTC: false })}
      </p>
      <p className="text-sm font-semibold text-blue-600 mt-1">
        Risk: {risk == null ? "—" : `${risk}%`}
      </p>
      <p className="text-xs text-gray-500 mt-1">
        {count} analysis{count !== 1 ? "es" : ""}
      </p>
    </div>
  );
};

export default function RiskTrendChart({ timeseries }) {
  const { data, stats, showDateOnTicks } = useMemo(() => {
    const ts = Array.isArray(timeseries) ? timeseries : [];
    if (ts.length === 0) {
      return { data: [], stats: { min: 0, max: 0, avg: 0 }, showDateOnTicks: false };
    }

    // Ensure numeric, sorted oldest->newest
    const sorted = [...ts]
      .map((d) => ({
        t: Number(d.t),
        avg_risk: d.avg_risk == null ? null : Number(d.avg_risk),
        count: Number(d.count ?? 0),
      }))
      .filter((d) => Number.isFinite(d.t))
      .sort((a, b) => a.t - b.t);

    const data = sorted.map((d) => ({
      t: d.t,
      avg_risk_pct: d.avg_risk == null ? null : Math.round(d.avg_risk * 100),
      count: d.count,
    }));

    const risks = data
      .map((d) => d.avg_risk_pct)
      .filter((v) => v != null && Number.isFinite(v));

    const min = risks.length ? Math.min(...risks) : 0;
    const max = risks.length ? Math.max(...risks) : 0;
    const avg = risks.length ? Math.round(risks.reduce((a, b) => a + b, 0) / risks.length) : 0;

    // If range crosses > 24h, show date+time ticks
    const spanSeconds = data.length >= 2 ? (data[data.length - 1].t - data[0].t) : 0;
    const showDateOnTicks = spanSeconds > 24 * 3600;

    return { data, stats: { min, max, avg }, showDateOnTicks };
  }, [timeseries]);

  if (!data.length) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-4">
        <div className="mb-3 text-sm font-semibold text-gray-900">Average risk over time</div>
        <div className="h-64 flex items-center justify-center text-gray-400">
          No trend data yet. Run more analyses to see patterns.
        </div>
      </div>
    );
  }

  const hasData = data.length > 1;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold text-gray-900">Average risk over time</div>
        <div className="text-xs text-gray-500">Risk %</div>
      </div>

      {!hasData ? (
        <div className="text-xs text-gray-500">Not enough points yet. Run a few more predictions.</div>
      ) : (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 5, right: 20, bottom: 10, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.25} />

              {/* ✅ TRUE time axis */}
              <XAxis
                dataKey="t"
                type="number"
                domain={["dataMin", "dataMax"]}
                tickFormatter={(v) => fmtTick(v, { showDate: showDateOnTicks, useUTC: false })}
                interval="preserveStartEnd"
                minTickGap={44}
                tick={{ fill: "#6b7280", fontSize: 11 }}
                tickCount={6}
              />

              <YAxis
                domain={[0, 100]}
                tickFormatter={(v) => `${v}`}
                tick={{ fill: "#6b7280", fontSize: 11 }}
              />

              <Tooltip content={<CustomTooltip />} />

              <Line
                type="monotone"
                dataKey="avg_risk_pct"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 5, strokeWidth: 2 }}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
        <div className="p-2 bg-gray-50 rounded">
          <span className="text-gray-500">Min</span>
          <div className="font-semibold text-gray-900">{stats.min}%</div>
        </div>
        <div className="p-2 bg-gray-50 rounded">
          <span className="text-gray-500">Max</span>
          <div className="font-semibold text-gray-900">{stats.max}%</div>
        </div>
        <div className="p-2 bg-gray-50 rounded">
          <span className="text-gray-500">Avg</span>
          <div className="font-semibold text-gray-900">{stats.avg}%</div>
        </div>
      </div>
    </div>
  );
}
