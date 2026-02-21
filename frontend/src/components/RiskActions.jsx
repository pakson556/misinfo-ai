import React, { useState } from "react";
import { AlertCircle, AlertTriangle, Info, CheckCircle, Eye, ChevronDown, ChevronUp } from "lucide-react";

const ACTIONS = {
  LOW: {
    icon: CheckCircle,
    color: "text-green-700",
    bg: "bg-green-50",
    border: "border-green-200",
    mainAction: "✅ Safe to share",
    items: [
      "Add a source if possible",
      "Avoid sensational framing",
      "Share with context"
    ]
  },
  MEDIUM: {
    icon: AlertTriangle,
    color: "text-yellow-700",
    bg: "bg-yellow-50",
    border: "border-yellow-200",
    mainAction: "⚠️ Verify before sharing",
    items: [
      "Check key claims against trusted sources",
      "Look for official statements",
      "Be cautious with emotional language",
      "Verify the original source"
    ]
  },
  HIGH: {
    icon: AlertCircle,
    color: "text-red-700",
    bg: "bg-red-50",
    border: "border-red-200",
    mainAction: "🚫 Do not share",
    items: [
      "Document details for reporting",
      "Warn contacts if already spreading",
      "Search for credible debunks",
      "Do not amplify until verified"
    ]
  },
};

export default function RiskActions({ riskBand, verdict, showDebug = false, debugInfo = null }) {
  const [showTechnical, setShowTechnical] = useState(false);
  
  // Use the misinformation risk band, not the verdict
  const band = (riskBand || "MEDIUM").toUpperCase();
  const config = ACTIONS[band] || ACTIONS.MEDIUM;
  const Icon = config.icon;

  return (
    <div className={`${config.bg} border ${config.border} rounded-lg p-4`}>
      {/* Main Action - Bold and Clear */}
      <div className="flex items-center gap-2 mb-3">
        <Icon className={`w-5 h-5 ${config.color}`} />
        <p className={`text-base font-semibold ${config.color}`}>
          {config.mainAction}
        </p>
      </div>

      {/* Supporting Actions */}
      <ul className="space-y-2 mb-3">
        {config.items.map((action, i) => (
          <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
            <span className={`${config.color} font-bold`}>•</span>
            <span>{action}</span>
          </li>
        ))}
      </ul>

      {/* Debug Toggle - Only visible if showDebug is true */}
      {showDebug && debugInfo && (
        <div className="mt-3 pt-3 border-t border-gray-200">
          <button
            onClick={() => setShowTechnical(!showTechnical)}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 transition-colors"
          >
            <Eye className="w-3 h-3" />
            {showTechnical ? "Hide" : "Show"} technical details
            {showTechnical ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
          
          {showTechnical && (
            <div className="mt-3 p-3 bg-gray-900 text-gray-100 rounded-lg text-xs font-mono space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-gray-400">Raw probability:</span>
                  <span className="ml-2 text-yellow-300">{debugInfo.raw_prob}%</span>
                </div>
                <div>
                  <span className="text-gray-400">Adjusted:</span>
                  <span className="ml-2 text-green-300">{debugInfo.adjusted_prob}%</span>
                </div>
                <div>
                  <span className="text-gray-400">Debunk score:</span>
                  <span className="ml-2 text-blue-300">{debugInfo.debunk_score}%</span>
                </div>
                <div>
                  <span className="text-gray-400">Stance:</span>
                  <span className="ml-2 text-purple-300">{debugInfo.stance}</span>
                </div>
              </div>
              <div className="pt-2 border-t border-gray-700">
                <span className="text-gray-400">Model breakdown:</span>
                <div className="mt-1 space-y-1">
                  {debugInfo.model_breakdown && Object.entries(debugInfo.model_breakdown).map(([key, value]) => (
                    <div key={key} className="flex justify-between">
                      <span className="text-gray-500">{key}:</span>
                      <span className="text-gray-300">{value}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}