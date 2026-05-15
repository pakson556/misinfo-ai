import React from "react";
import {
  AlertCircle,
  AlertTriangle,
  Award,
  ExternalLink,
  Globe,
  Microscope,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";

function claimStyles(verdict) {
  switch ((verdict || "").toUpperCase()) {
    case "LIKELY_TRUE":
      return {
        wrap: "border-emerald-200",
        header: "bg-emerald-50 border-emerald-200",
        badge: "bg-emerald-100 text-emerald-700 border-emerald-200",
      };
    case "LIKELY_FALSE":
      return {
        wrap: "border-rose-200",
        header: "bg-rose-50 border-rose-200",
        badge: "bg-rose-100 text-rose-700 border-rose-200",
      };
    case "MIXED":
      return {
        wrap: "border-amber-200",
        header: "bg-amber-50 border-amber-200",
        badge: "bg-amber-100 text-amber-700 border-amber-200",
      };
    default:
      return {
        wrap: "border-gray-200",
        header: "bg-gray-50 border-gray-200",
        badge: "bg-gray-100 text-gray-700 border-gray-200",
      };
  }
}

export default function InternetVerificationPanel({ internet }) {
  if (!internet || !internet.enabled) return null;

  const verdict = (internet.overall_verdict || "UNVERIFIED").toUpperCase();
  const confidencePct = Math.round((internet.overall_confidence || 0) * 100);

  const getVerdictConfig = () => {
    switch (verdict) {
      case "LIKELY_TRUE":
        return {
          bg: "bg-emerald-50",
          border: "border-emerald-200",
          text: "text-emerald-700",
          icon: <ShieldCheck className="w-5 h-5 text-emerald-600" />,
          badge: "bg-emerald-100 text-emerald-700 border-emerald-200",
          label: "Likely True",
          message: "Trusted online sources support these claims.",
        };
      case "LIKELY_FALSE":
        return {
          bg: "bg-rose-50",
          border: "border-rose-200",
          text: "text-rose-700",
          icon: <ShieldAlert className="w-5 h-5 text-rose-600" />,
          badge: "bg-rose-100 text-rose-700 border-rose-200",
          label: "Likely False",
          message: "Trusted online sources contradict these claims.",
        };
      case "MIXED":
        return {
          bg: "bg-amber-50",
          border: "border-amber-200",
          text: "text-amber-700",
          icon: <AlertTriangle className="w-5 h-5 text-amber-600" />,
          badge: "bg-amber-100 text-amber-700 border-amber-200",
          label: "Mixed Evidence",
          message: "Online evidence is mixed or conflicting.",
        };
      default:
        return {
          bg: "bg-gray-50",
          border: "border-gray-200",
          text: "text-gray-700",
          icon: <Search className="w-5 h-5 text-gray-600" />,
          badge: "bg-gray-100 text-gray-700 border-gray-200",
          label: "Unverified",
          message: internet.summary_note || "Limited online evidence found.",
        };
    }
  };

  const config = getVerdictConfig();
  const hasScientificConsensus = internet.claims?.some(
    (c) => c.scientific_consensus
  );

  return (
    <div className={`rounded-xl border ${config.border} overflow-hidden`}>
      <div className={`${config.bg} p-5 border-b ${config.border}`}>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex items-start gap-3">
            <div className="mt-0.5">{config.icon}</div>
            <div>
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <h3 className="font-semibold text-gray-900">
                  Internet Verification
                </h3>

                <span
                  className={`text-xs px-2 py-1 rounded-full border ${config.badge}`}
                >
                  {config.label}
                </span>

                {hasScientificConsensus && (
                  <span className="text-xs px-2 py-1 rounded-full bg-purple-100 text-purple-700 border border-purple-200 flex items-center gap-1">
                    <Microscope className="w-3 h-3" />
                    Scientific Consensus
                  </span>
                )}
              </div>

              <p className="text-sm text-gray-700">{config.message}</p>
            </div>
          </div>

          <div className="text-right">
            <p className="text-xs text-gray-500">Confidence</p>
            <p className={`text-2xl font-bold ${config.text}`}>
              {confidencePct}%
            </p>
          </div>
        </div>

        {internet.error && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <div className="flex items-start gap-2">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>Internet verification error: {internet.error}</span>
            </div>
          </div>
        )}
      </div>

      {internet.claims?.length > 0 && (
        <div className="p-5 bg-white">
          <h4 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <Shield className="w-4 h-4" />
            Verified Claims
          </h4>

          <div className="space-y-4">
            {internet.claims.map((claim, idx) => {
              const styles = claimStyles(claim.verdict);
              const isScientific = claim.scientific_consensus;
              const claimConfidence = Math.round((claim.confidence || 0) * 100);
              const supportScore =
                Math.round((claim.support_score || 0) * 100) / 100;
              const refuteScore =
                Math.round((claim.refute_score || 0) * 100) / 100;

              return (
                <div
                  key={idx}
                  className={`rounded-lg border overflow-hidden ${styles.wrap}`}
                >
                  <div className={`p-4 border-b ${styles.header}`}>
                    <p className="text-sm font-medium text-gray-900 mb-3">
                      "{claim.claim}"
                    </p>

                    <div className="flex items-center gap-3 flex-wrap">
                      <span
                        className={`text-xs px-2 py-1 rounded-full border ${styles.badge}`}
                      >
                        {(claim.verdict || "UNVERIFIED").replaceAll("_", " ")}
                      </span>

                      <span className="text-xs text-gray-600">
                        Confidence: {claimConfidence}%
                      </span>

                      {isScientific && (
                        <span className="text-xs px-2 py-1 rounded-full bg-purple-100 text-purple-700 border border-purple-200 flex items-center gap-1">
                          <Award className="w-3 h-3" />
                          Scientific Consensus
                        </span>
                      )}
                    </div>

                    <div className="mt-2 flex gap-3 text-xs text-gray-500 flex-wrap">
                      <span>Support: {supportScore}</span>
                      <span>Refute: {refuteScore}</span>
                    </div>
                  </div>

                  {claim.sources?.length > 0 ? (
                    <div className="p-4 bg-gray-50">
                      <p className="text-xs font-medium text-gray-500 mb-2">
                        Evidence Sources
                      </p>

                      <div className="space-y-2">
                        {claim.sources.slice(0, 3).map((source, sidx) => (
                          <a
                            key={sidx}
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="block rounded-lg border border-gray-200 bg-white p-3 hover:shadow-sm transition"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0 flex-1">
                                <p className="text-sm font-medium text-gray-900 truncate">
                                  {source.title || source.domain || "Source"}
                                </p>

                                <div className="flex items-center gap-2 mt-1 flex-wrap">
                                  <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                                    {source.source_type || "general"}
                                  </span>

                                  <span className="text-xs text-gray-500">
                                    Credibility:{" "}
                                    {Math.round(
                                      (source.credibility || 0) * 100
                                    )}
                                    %
                                  </span>

                                  {source.evidence_direction ? (
                                    <span className="text-xs text-gray-500 capitalize">
                                      {source.evidence_direction}
                                    </span>
                                  ) : null}
                                </div>

                                {source.snippet && (
                                  <p className="text-xs text-gray-600 mt-2 line-clamp-2">
                                    {source.snippet}
                                  </p>
                                )}
                              </div>

                              <ExternalLink className="w-4 h-4 text-gray-400 flex-shrink-0" />
                            </div>
                          </a>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <div className="p-4 bg-gray-50">
                      <p className="text-xs font-medium text-gray-500 mb-1">
                        Evidence Sources
                      </p>
                      <p className="text-sm text-gray-600">
                        No supporting or refuting sources were returned by the
                        verification engine for this claim.
                      </p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {internet.sources?.length > 0 &&
        (!internet.claims || internet.claims.length === 0) && (
          <div className="p-5 bg-white">
            <h4 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Globe className="w-4 h-4" />
              Sources
            </h4>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {internet.sources.slice(0, 6).map((src, idx) => (
                <a
                  key={idx}
                  href={src.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-start justify-between gap-3 p-3 rounded-lg border border-gray-200 bg-gray-50 hover:bg-gray-100 transition"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {src.title || src.domain || "Source"}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {src.domain || "Unknown domain"}
                    </p>
                  </div>

                  <ExternalLink className="w-4 h-4 text-gray-400 flex-shrink-0" />
                </a>
              ))}
            </div>
          </div>
        )}
    </div>
  );
}