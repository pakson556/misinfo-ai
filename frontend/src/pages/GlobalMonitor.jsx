import React, { useEffect, useState } from "react";
import {
  AlertTriangle,
  Globe,
  RefreshCw,
  ExternalLink,
  Clock,
  Filter,
  Activity,
  BarChart3,
  TrendingUp,
  Radio,
  ArrowUpRight,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Info,
} from "lucide-react";

const riskBadgeStyles = {
  HIGH: "bg-red-100 text-red-800 border-red-200",
  MEDIUM: "bg-amber-100 text-amber-800 border-amber-200",
  LOW: "bg-green-100 text-green-800 border-green-200",
};

const sourceStyles = {
  BBC: "bg-blue-50 text-blue-700 border-blue-200",
  Reuters: "bg-slate-50 text-slate-700 border-slate-200",
  Reddit: "bg-orange-50 text-orange-700 border-orange-200",
  "Google News": "bg-gray-50 text-gray-700 border-gray-200",
  AFP: "bg-sky-50 text-sky-700 border-sky-200",
  DW: "bg-cyan-50 text-cyan-700 border-cyan-200",
};

const signalStyles = {
  "HIGH PRIORITY": "bg-red-50 text-red-700 border-red-200",
  "NEWS SIGNAL": "bg-blue-50 text-blue-700 border-blue-200",
  "SOCIAL SIGNAL": "bg-orange-50 text-orange-700 border-orange-200",
  "SOCIAL SURGE": "bg-purple-50 text-purple-700 border-purple-200",
  "LIVE SIGNAL": "bg-indigo-50 text-indigo-700 border-indigo-200",
  MONITOR: "bg-gray-50 text-gray-700 border-gray-200",
};

const getRiskLevel = (risk) => {
  if (risk >= 0.65) return "HIGH";
  if (risk >= 0.35) return "MEDIUM";
  return "LOW";
};

const formatTime = (timestamp) => {
  if (!timestamp) return null;
  try {
    return new Date(timestamp).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return null;
  }
};

const titleCase = (value) => {
  if (!value) return "Other";
  return String(value)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
};

const StatCard = ({ icon: Icon, label, value, subtitle }) => (
  <div className="bg-white rounded-lg border border-gray-200 p-4">
    <div className="flex items-center gap-2 text-gray-600 mb-2">
      <Icon size={16} />
      <span className="text-sm font-medium">{label}</span>
    </div>
    <div className="text-2xl font-semibold text-gray-900">{value}</div>
    {subtitle && <div className="text-xs text-gray-500 mt-1">{subtitle}</div>}
  </div>
);

const SmallChip = ({ children, className = "" }) => (
  <span
    className={`inline-flex items-center px-2 py-0.5 rounded text-xs border ${className}`}
  >
    {children}
  </span>
);

const ExplanationSection = ({ explanation }) => {
  if (!explanation) return null;

  const reasons = Array.isArray(explanation?.reasons) ? explanation.reasons : [];
  const triggers = Array.isArray(explanation?.triggers)
    ? explanation.triggers
    : [];

  const matchedTerms = explanation?.matched_terms || {};
  const allMatchedGroups = Object.entries(matchedTerms).filter(
    ([, values]) => Array.isArray(values) && values.length > 0
  );

  return (
    <div className="mt-3 rounded-md border border-gray-200 bg-gray-50 p-3">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles size={14} className="text-indigo-500" />
        <p className="text-sm font-medium text-gray-800">Explainability details</p>
      </div>

      {triggers.length > 0 && (
        <div className="mb-3">
          <p className="text-xs font-medium text-gray-500 mb-1">Triggers</p>
          <div className="flex flex-wrap gap-1.5">
            {triggers.map((trigger, idx) => (
              <SmallChip
                key={`${trigger}-${idx}`}
                className="bg-white text-gray-700 border-gray-200"
              >
                {titleCase(trigger)}
              </SmallChip>
            ))}
          </div>
        </div>
      )}

      {reasons.length > 0 && (
        <div className="mb-3">
          <p className="text-xs font-medium text-gray-500 mb-1">Reasons</p>
          <ul className="space-y-1">
            {reasons.map((reason, idx) => (
              <li key={idx} className="text-sm text-gray-700 flex gap-2">
                <span className="text-gray-400 mt-1">•</span>
                <span>{reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {allMatchedGroups.length > 0 && (
        <div className="mb-3">
          <p className="text-xs font-medium text-gray-500 mb-1">Matched terms</p>
          <div className="space-y-2">
            {allMatchedGroups.map(([group, values]) => (
              <div key={group}>
                <p className="text-xs text-gray-500 mb-1">{titleCase(group)}</p>
                <div className="flex flex-wrap gap-1.5">
                  {values.map((term, idx) => (
                    <SmallChip
                      key={`${group}-${term}-${idx}`}
                      className="bg-white text-gray-700 border-gray-200"
                    >
                      {term}
                    </SmallChip>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {explanation?.confidence_note && (
        <div className="flex items-start gap-2 text-xs text-gray-600 bg-white border border-gray-200 rounded-md p-2">
          <Info size={13} className="mt-0.5 text-gray-400" />
          <span>{explanation.confidence_note}</span>
        </div>
      )}
    </div>
  );
};

const SignalItem = ({ item }) => {
  const [expanded, setExpanded] = useState(false);

  const riskLevel = getRiskLevel(item?.risk || 0);
  const source = item?.source || item?.publisher || "Unknown";
  const title = item?.claim || item?.title || "Untitled";
  const verdict = item?.verdict || "LIVE SIGNAL";
  const signalType = item?.signal_type || "LIVE SIGNAL";
  const topic = item?.topic || "other";
  const timeStr = formatTime(
    item?.published_iso || item?.published || item?.timestamp || item?.review_date
  );

  const hasExplanation = !!item?.explanation;
  const reasonsCount = Array.isArray(item?.explanation?.reasons)
    ? item.explanation.reasons.length
    : 0;

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 hover:border-gray-300 hover:shadow-sm transition-shadow">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
          </span>
          <span className="text-xs font-medium text-gray-500">LIVE</span>
          {timeStr && (
            <>
              <span className="text-gray-300">•</span>
              <span className="text-xs text-gray-400">{timeStr}</span>
            </>
          )}
        </div>

        {item?.url && (
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
          >
            View <ArrowUpRight size={14} />
          </a>
        )}
      </div>

      <h3 className="font-medium text-gray-900 mb-3">{title}</h3>

      <div className="flex flex-wrap gap-1.5 mb-3">
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${riskBadgeStyles[riskLevel]}`}
        >
          {riskLevel === "HIGH" && <AlertTriangle size={12} className="mr-1" />}
          {riskLevel}
        </span>

        <span
          className={`inline-flex items-center px-2 py-0.5 rounded text-xs border ${sourceStyles[source] || "bg-gray-50 text-gray-700 border-gray-200"}`}
        >
          {source}
        </span>

        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs border bg-gray-50 text-gray-700 border-gray-200">
          {verdict}
        </span>

        <span
          className={`inline-flex items-center px-2 py-0.5 rounded text-xs border ${signalStyles[signalType] || "bg-gray-50 text-gray-700 border-gray-200"}`}
        >
          {signalType}
        </span>

        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs border bg-gray-50 text-gray-700 border-gray-200">
          {topic}
        </span>

        {item?.engagement ? (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs border bg-amber-50 text-amber-700 border-amber-200">
            <TrendingUp size={12} className="mr-1" />
            {item.engagement}
          </span>
        ) : null}
      </div>

      <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded border border-gray-100">
        <div className="font-medium text-gray-700 mb-1">Why flagged</div>
        <p>{item?.why_flagged || "Detected in monitoring feeds."}</p>
      </div>

      {hasExplanation && (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="inline-flex items-center gap-2 text-sm text-indigo-600 hover:text-indigo-800"
          >
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            {expanded
              ? "Hide explanation"
              : `Show explanation${reasonsCount > 0 ? ` (${reasonsCount})` : ""}`}
          </button>

          {expanded && <ExplanationSection explanation={item.explanation} />}
        </div>
      )}
    </div>
  );
};

export default function GlobalMonitor() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [feed, setFeed] = useState([]);
  const [stats, setStats] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [category, setCategory] = useState("all");

  const fetchData = async () => {
    try {
      setError("");
      setLoading(true);

      const response = await fetch("http://127.0.0.1:8000/live-feed?limit=20");
      if (!response.ok) throw new Error("Failed to fetch data");

      const data = await response.json();
      setFeed(data.items || []);
      setStats(data.stats || null);
      setLastUpdate(new Date());
    } catch (err) {
      setError(err.message || "Connection error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    const interval = setInterval(fetchData, 90000);
    return () => clearInterval(interval);
  }, []);

  const categories = [...new Set(feed.map((item) => item?.topic).filter(Boolean))].sort();

  const filteredFeed = feed.filter((item) => {
    if (category === "all") return true;
    return (item?.topic || "other") === category;
  });

  const activeCount = filteredFeed.length;

  const highRiskCount = filteredFeed.filter(
    (item) => getRiskLevel(item?.risk || 0) === "HIGH"
  ).length;

  const mentionCount = filteredFeed.reduce(
    (sum, item) => sum + (item?.engagement || 1),
    0
  );

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 bg-white rounded-lg border border-gray-200">
            <Globe size={20} className="text-blue-600" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-gray-900">Global Monitor</h1>
            <p className="text-sm text-gray-500">Real-time signal monitoring</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <StatCard
            icon={Activity}
            label="Active"
            value={activeCount}
            subtitle="Current signals"
          />
          <StatCard
            icon={AlertTriangle}
            label="High Risk"
            value={highRiskCount}
            subtitle={highRiskCount > 0 ? "Needs attention" : "All clear"}
          />
          <StatCard
            icon={BarChart3}
            label="Mentions"
            value={mentionCount}
            subtitle="Total engagement"
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2">
            <button
              onClick={fetchData}
              disabled={loading}
              className="flex items-center gap-2 px-3 py-1.5 text-sm bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
            >
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
              Refresh
            </button>

            <div className="relative">
              <Filter
                size={14}
                className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400"
              />
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="pl-8 pr-6 py-1.5 text-sm bg-white border border-gray-300 rounded-md appearance-none cursor-pointer hover:border-gray-400"
              >
                <option value="all">All categories</option>
                {categories.map((cat) => (
                  <option key={cat} value={cat}>
                    {titleCase(cat)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {lastUpdate && (
            <div className="flex items-center gap-1.5 text-xs text-gray-500">
              <Clock size={12} />
              <span>Updated {lastUpdate.toLocaleTimeString()}</span>
            </div>
          )}
        </div>

        {loading && (
          <div className="text-center py-12 text-gray-500">
            <RefreshCw size={24} className="animate-spin mx-auto mb-3" />
            <p>Loading feed...</p>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
            <p className="font-medium">Error</p>
            <p className="text-sm">{error}</p>
          </div>
        )}

        {!loading && !error && (
          <div className="space-y-3">
            {filteredFeed.length > 0 ? (
              filteredFeed.map((item, idx) => (
                <SignalItem key={`${item?.source || idx}-${idx}`} item={item} />
              ))
            ) : (
              <div className="bg-white border border-gray-200 rounded-lg p-12 text-center">
                <Radio size={32} className="text-gray-300 mx-auto mb-3" />
                <p className="text-gray-500">No signals to display</p>
                <p className="text-sm text-gray-400 mt-1">
                  Check back later or adjust filters
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}