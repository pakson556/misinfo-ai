import React, { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronUp, Eye, ShieldAlert, ShieldCheck } from "lucide-react";

const ACTIONS = {
  LOW: {
    icon: ShieldCheck,
    color: "text-green-700",
    bg: "bg-green-50",
    border: "border-green-200",
    mainAction: "Low-risk signal",
    items: [
      "Sharing risk appears lower, but still verify if the claim is high-impact or time-sensitive.",
      "Check the original source if the post makes strong factual claims.",
      "Be careful with screenshots or reposted summaries that remove context.",
    ],
  },
  MEDIUM: {
    icon: AlertTriangle,
    color: "text-yellow-700",
    bg: "bg-yellow-50",
    border: "border-yellow-200",
    mainAction: "Verify before sharing",
    items: [
      "Check key claims against trusted sources.",
      "Look for official statements or authoritative reporting.",
      "Be cautious with emotional or urgent wording.",
    ],
  },
  HIGH: {
    icon: ShieldAlert,
    color: "text-red-700",
    bg: "bg-red-50",
    border: "border-red-200",
    mainAction: "Do not trust without strong verification",
    items: [
      "Avoid sharing until independently confirmed.",
      "Look for fact-check coverage and official evidence.",
      "Treat sensational or conspiratorial framing as a warning sign.",
    ],
  },
};

function normaliseBand(riskBand, verdict) {
  const band = String(riskBand || "").toUpperCase();
  const v = String(verdict || "").toUpperCase();

  if (v === "LIKELY_MISINFORMATION" || v === "DO_NOT_SHARE") return "HIGH";
  if (v === "VERIFY_REQUIRED") return "MEDIUM";
  if (v === "SAFE_TO_SHARE" && !band) return "LOW";

  if (band === "LOW" || band === "MEDIUM" || band === "HIGH") return band;
  return "MEDIUM";
}

export default function RiskActions({ riskBand, verdict, showDebug = false, debugInfo = null }) {
  const [showTechnical, setShowTechnical] = useState(false);

  const band = normaliseBand(riskBand, verdict);
  const config = ACTIONS[band] || ACTIONS.MEDIUM;
  const Icon = config.icon;

  return (
    <div className={`${config.bg} border ${config.border} rounded-xl p-5`}>
      <div className="flex items-center gap-2 mb-4">
        <Icon className={`w-5 h-5 ${config.color}`} />
        <p className={`text-base font-semibold ${config.color}`}>{config.mainAction}</p>
      </div>

      {verdict ? (
        <p className="text-sm text-gray-600 mb-4">System verdict: {verdict.replaceAll("_", " ")}</p>
      ) : null}

      <ul className="space-y-2">
        {config.items.map((action, i) => (
          <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
            <span className={`${config.color} font-bold mt-0.5`}>•</span>
            <span>{action}</span>
          </li>
        ))}
      </ul>

      {showDebug && debugInfo && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <button
            onClick={() => setShowTechnical(!showTechnical)}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 transition"
          >
            <Eye className="w-3 h-3" />
            {showTechnical ? "Hide" : "Show"} technical details
            {showTechnical ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>

          {showTechnical && (
            <div className="mt-3 p-3 bg-gray-900 text-gray-100 rounded-lg text-xs font-mono whitespace-pre-wrap">
              {JSON.stringify(debugInfo, null, 2)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}