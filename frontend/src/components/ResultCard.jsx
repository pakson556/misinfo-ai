// src/components/ResultCard.jsx
import React, { useMemo, useState } from "react";
import {
  ShieldAlert,
  CheckCircle,
  Info,
  Brain,
  Network,
  Users,
  AlertTriangle,
  TrendingUp,
  Globe,
  ChevronDown,
  ChevronUp,
  BadgeCheck,
  SearchCheck,
} from "lucide-react";
import RiskActions from "./RiskActions.jsx";

function clampPercent(value, fallback = 0) {
  const n = Number(value);
  if (Number.isNaN(n)) return fallback;
  if (n < 0) return 0;
  if (n > 100) return 100;
  return Math.round(n);
}

function toPercent(value, fallback = 0) {
  const n = Number(value);
  if (Number.isNaN(n)) return fallback;
  return n <= 1 ? clampPercent(n * 100) : clampPercent(n);
}

function normaliseRiskBand(_band, scorePercent = 0) {
  if (scorePercent >= 45) return "HIGH";
  if (scorePercent >= 15) return "MEDIUM";
  return "LOW";
}

function formatVerdict(verdict, riskBand) {
  const raw = String(verdict || "").trim();
  if (!raw) return riskBand === "LOW" ? "SAFE TO SHARE" : "VERIFY BEFORE SHARING";
  return raw.replaceAll("_", " ").toUpperCase();
}

function bandStyles(band) {
  const b = (band || "MEDIUM").toUpperCase();

  if (b === "LOW") {
    return {
      border: "border-emerald-500/30",
      iconBg: "bg-gradient-to-br from-emerald-500 to-emerald-600",
      icon: <CheckCircle className="text-white w-8 h-8" />,
      gradient: "from-emerald-500/20 to-emerald-600/5",
      text: "text-emerald-300",
      glow: "shadow-emerald-500/20",
      pill: "bg-emerald-500/15 text-emerald-200 border border-emerald-500/25",
    };
  }

  if (b === "HIGH") {
    return {
      border: "border-red-500/30",
      iconBg: "bg-gradient-to-br from-red-500 to-red-600",
      icon: <ShieldAlert className="text-white w-8 h-8" />,
      gradient: "from-red-500/20 to-red-600/5",
      text: "text-red-300",
      glow: "shadow-red-500/20",
      pill: "bg-red-500/15 text-red-200 border border-red-500/25",
    };
  }

  return {
    border: "border-amber-500/30",
    iconBg: "bg-gradient-to-br from-amber-500 to-orange-500",
    icon: <AlertTriangle className="text-white w-8 h-8" />,
    gradient: "from-amber-500/20 to-orange-500/5",
    text: "text-amber-200",
    glow: "shadow-amber-500/20",
    pill: "bg-amber-500/15 text-amber-100 border border-amber-500/25",
  };
}

function toneBadge(stance) {
  const s = String(stance || "neutral").toLowerCase();

  if (s === "credible") return { label: "Credible", color: "text-emerald-200" };
  if (s === "warning") return { label: "Warning / Corrective", color: "text-sky-200" };
  if (s === "debunking") return { label: "Debunking", color: "text-cyan-200" };
  if (s === "spreading") return { label: "Potentially Spreading", color: "text-red-200" };
  if (s === "satire") return { label: "Satire / Parody", color: "text-fuchsia-200" };

  return { label: "Neutral", color: "text-slate-100" };
}

function verificationTone(status) {
  const s = String(status || "").toLowerCase();

  if (s.includes("true") || s.includes("supported")) {
    return {
      label: "Likely True",
      color: "text-emerald-200",
      subtext: "Trusted online sources support these claims.",
    };
  }
  if (s.includes("mixed") || s.includes("partial")) {
    return {
      label: "Mixed Evidence",
      color: "text-amber-200",
      subtext: "Online evidence is mixed or incomplete.",
    };
  }
  if (s.includes("false") || s.includes("refuted")) {
    return {
      label: "Likely False",
      color: "text-red-200",
      subtext: "Trusted online sources refute these claims.",
    };
  }
  return {
    label: "Unverified",
    color: "text-slate-100",
    subtext: "Trusted online evidence was insufficient to confirm or refute these claims.",
  };
}

function scoreLabel(scorePercent) {
  if (scorePercent >= 45) return "High";
  if (scorePercent >= 15) return "Medium";
  return "Low";
}

function getModelConfidence(result, likelihoodPercent, verificationConfidence) {
  const candidates = [
    result?.model_confidence,
    result?.confidence,
    result?.analysis_confidence,
    result?.ensemble_confidence,
  ];

  for (const c of candidates) {
    const n = Number(c);
    if (!Number.isNaN(n)) {
      return n <= 1 ? clampPercent(n * 100) : clampPercent(n);
    }
  }

  if (typeof verificationConfidence === "number") {
    return clampPercent(verificationConfidence);
  }

  const distance = Math.abs(likelihoodPercent - 50);
  return clampPercent(55 + distance * 0.9);
}

function getRiskExplanation(riskBand, likelihoodPercent, confidencePercent) {
  const level =
    riskBand === "LOW" ? "low" : riskBand === "HIGH" ? "high" : "moderate";

  return `The model estimates a ${likelihoodPercent}% likelihood that this content may be misleading, with ${confidencePercent}% confidence in this ${level}-risk assessment.`;
}

function cleanSummaryText(summary = "") {
  let text = String(summary || "").trim();
  if (!text) return "";

  text = text.replace(/\s+/g, " ").trim();

  text = text.replace(
    /The model outputs indicate a low risk of misinformation, with an estimated probability of \d+%\.?/gi,
    ""
  );
  text = text.replace(
    /The model outputs indicate a medium risk of misinformation, with an estimated probability of \d+%\.?/gi,
    ""
  );
  text = text.replace(
    /The model outputs indicate a high risk of misinformation, with an estimated probability of \d+%\.?/gi,
    ""
  );

  text = text.replace(
    /As such, it is essential to verify the claim if it is high-impact or time-sensitive\.?/gi,
    ""
  );

  text = text.replace(/\s+\./g, ".");
  text = text.replace(/\.\s*\./g, ".");
  return text.trim();
}

function buildContentAnalysis({
  summary,
  riskBand,
  likelihoodPercent,
  confidencePercent,
  verificationLabel,
  verificationConfidence,
}) {
  const cleanSummary = cleanSummaryText(summary);
  const riskExplanation = getRiskExplanation(riskBand, likelihoodPercent, confidencePercent);
  const verificationText = `Internet verification suggests ${verificationLabel.toLowerCase()}${
    typeof verificationConfidence === "number"
      ? ` with ${verificationConfidence}% verification confidence.`
      : "."
  }`;

  if (cleanSummary) {
    return `${cleanSummary} ${riskExplanation} ${verificationText}`;
  }

  if (riskBand === "LOW") {
    return `The content appears broadly consistent with established or credible information. ${riskExplanation} ${verificationText}`;
  }

  if (riskBand === "HIGH") {
    return `The content shows patterns commonly associated with misleading or unsupported claims. ${riskExplanation} ${verificationText}`;
  }

  return `The content contains some features that could be factual or misleading depending on context. ${riskExplanation} ${verificationText}`;
}

function SectionCard({ icon, title, children, right }) {
  return (
    <div className="rounded-2xl border border-white/15 bg-slate-900/90 p-5 shadow-lg">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-white/10 p-2">{icon}</div>
          <h3 className="text-base font-semibold text-white">{title}</h3>
        </div>
        {right}
      </div>
      <div className="text-slate-100">{children}</div>
    </div>
  );
}

function MetricBox({ label, value, subtext }) {
  return (
    <div className="rounded-2xl border border-white/15 bg-slate-800/95 p-4 shadow-sm">
      <p className="text-xs uppercase tracking-wide text-slate-300">{label}</p>
      <p className="mt-2 text-2xl font-bold text-white">{value}</p>
      {subtext ? <p className="mt-2 text-sm text-slate-100">{subtext}</p> : null}
    </div>
  );
}

function TriggerBar({ name, score, explanation }) {
  const pct = toPercent(score);

  return (
    <div className="rounded-2xl border border-white/15 bg-slate-800/95 p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-white">{name || "Signal"}</h4>
          <p className="mt-2 text-sm text-slate-100">{explanation || "No explanation available."}</p>
        </div>
        <span className="shrink-0 text-sm font-semibold text-white">{pct}%</span>
      </div>
      <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-white/10">
        <div
          className="h-full rounded-full bg-gradient-to-r from-sky-400 to-cyan-300"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function EvidenceSource({ source }) {
  const credibility = toPercent(source?.credibility ?? source?.credibility_score ?? 0);
  const type = String(source?.type || source?.category || "source");
  const title = source?.title || source?.name || "Untitled source";
  const snippet = source?.snippet || source?.summary || source?.text || "";
  const url = source?.url;

  return (
    <div className="rounded-2xl border border-white/15 bg-slate-800/95 p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-sm font-semibold text-white">{title}</h4>
        <span className="rounded-full bg-white/10 px-2 py-1 text-xs text-slate-100">{type}</span>
        <span className="rounded-full bg-emerald-500/15 px-2 py-1 text-xs text-emerald-200">
          Credibility: {credibility}%
        </span>
      </div>

      {snippet ? <p className="mt-3 text-sm leading-6 text-slate-100">{snippet}</p> : null}

      {url ? (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex text-sm font-medium text-sky-200 hover:text-sky-100"
        >
          Open source
        </a>
      ) : null}
    </div>
  );
}

function ClaimCard({ claim }) {
  const label = String(claim?.verdict || claim?.label || claim?.status || "UNVERIFIED").toUpperCase();
  const confidence = claim?.confidence != null ? toPercent(claim.confidence) : null;

  const support =
    typeof claim?.support_score === "number"
      ? Math.round(claim.support_score * 100) / 100
      : typeof claim?.support === "number"
        ? Math.round(claim.support * 100) / 100
        : null;

  const refute =
    typeof claim?.refute_score === "number"
      ? Math.round(claim.refute_score * 100) / 100
      : typeof claim?.refute === "number"
        ? Math.round(claim.refute * 100) / 100
        : null;

  const sources = Array.isArray(claim?.sources) ? claim.sources : [];

  const hasPositiveSupport = support !== null && support > 0;
  const hasPositiveRefute = refute !== null && refute > 0;
  const noDirectEvidence =
    (support === null || support === 0) &&
    (refute === null || refute === 0) &&
    sources.length === 0;

  const pillClass =
    label.includes("TRUE") || label.includes("SUPPORTED") || label.includes("LIKELY_TRUE")
      ? "bg-emerald-500/15 text-emerald-200 border border-emerald-500/25"
      : label.includes("FALSE") || label.includes("REFUTED") || label.includes("LIKELY_FALSE")
        ? "bg-red-500/15 text-red-200 border border-red-500/25"
        : label.includes("MIXED")
          ? "bg-amber-500/15 text-amber-100 border border-amber-500/25"
          : "bg-slate-500/15 text-slate-100 border border-slate-500/25";

  return (
    <div className="rounded-2xl border border-white/15 bg-slate-900/90 p-4 shadow-sm">
      <p className="text-sm leading-6 text-white">“{claim?.claim || claim?.text || "Unknown claim"}”</p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${pillClass}`}>
          {label.replaceAll("_", " ")}
        </span>

        {confidence !== null ? (
          <span className="rounded-full bg-white/10 px-3 py-1 text-xs text-slate-100">
            Confidence: {confidence}%
          </span>
        ) : null}

        {hasPositiveSupport ? (
          <span className="rounded-full bg-white/10 px-3 py-1 text-xs text-slate-100">
            Support evidence: {support}
          </span>
        ) : null}

        {hasPositiveRefute ? (
          <span className="rounded-full bg-white/10 px-3 py-1 text-xs text-slate-100">
            Refuting evidence: {refute}
          </span>
        ) : null}

        {noDirectEvidence ? (
          <span className="rounded-full bg-white/10 px-3 py-1 text-xs text-slate-100">
            No direct evidence found
          </span>
        ) : null}
      </div>

      {sources.length > 0 ? (
        <div className="mt-4 space-y-3">
          <p className="text-sm font-semibold text-white">Evidence Sources</p>
          {sources.map((src, idx) => (
            <EvidenceSource key={`${claim?.claim || "claim"}-${idx}`} source={src} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

export default function ResultCard({ result }) {
  const [showDebug, setShowDebug] = useState(false);
  const [showAllClaims, setShowAllClaims] = useState(true);

  const derived = useMemo(() => {
    if (!result) return null;

    const misinformationProbRaw =
      result?.misinfo_probability ??
      result?.probability ??
      result?.risk_probability ??
      result?.misinformation_probability ??
      result?.scores?.misinformation ??
      result?.misinformation?.probability ??
      0;

    const misinformationLikelihood = toPercent(misinformationProbRaw);

    const riskBand = normaliseRiskBand(
      result?.risk_band || result?.risk || result?.misinformation?.band,
      misinformationLikelihood
    );
    const styles = bandStyles(riskBand);

    const verification = result?.internet_verification || {};
    const verificationStatus = verification?.overall_verdict || "unverified";
    const verificationConfidenceRaw =
      verification?.overall_confidence ?? verification?.confidence;
    const verificationConfidence =
      verificationConfidenceRaw != null ? toPercent(verificationConfidenceRaw) : null;

    const modelConfidence = getModelConfidence(
      result,
      misinformationLikelihood,
      verificationConfidence
    );

    const manipulationIntensityRaw =
      result?.manipulation_tactics?.intensity ??
      result?.manipulation_intensity ??
      result?.engagement_intensity ??
      result?.signals_score ??
      result?.analyst?.average_trigger_score ??
      0;

    const manipulationIntensity = toPercent(manipulationIntensityRaw);

    const stance =
      result?.misinformation?.stance || result?.stance || result?.tone || "neutral";
    const tone = toneBadge(stance);
    const verificationUi = verificationTone(verificationStatus);

    const claims = Array.isArray(verification?.claims) ? verification.claims : [];
    const analyst = result?.analyst || {};
    const triggers = Array.isArray(analyst?.triggers)
      ? analyst.triggers
      : Array.isArray(result?.triggers)
        ? result.triggers
        : [];

    const propagation = analyst?.propagation_dynamics || result?.propagation_dynamics || {};

    const whyShare =
      analyst?.human_susceptibility_logic ||
      result?.human_susceptibility_logic ||
      "This content may be shared because it appeals to emotion, personal relevance, or distrust of institutions.";

    const algorithmicAdvantage =
      analyst?.algorithmic_advantage ||
      result?.algorithmic_advantage ||
      "The model detected linguistic patterns commonly associated with misleading content, including uncertainty framing, distrust cues, and calls to action.";

    const summary =
      result?.explanation?.user_summary ||
      result?.user_summary ||
      result?.final_explanation ||
      result?.content_analysis ||
      result?.explanation?.final_explanation ||
      "";

    const contentAnalysis = buildContentAnalysis({
      summary,
      riskBand,
      likelihoodPercent: misinformationLikelihood,
      confidencePercent: modelConfidence,
      verificationLabel: verificationUi.label,
      verificationConfidence,
    });

    const reasons =
      Array.isArray(result?.explanation?.user_reasons) && result.explanation.user_reasons.length > 0
        ? result.explanation.user_reasons
        : Array.isArray(result?.user_reasons) && result.user_reasons.length > 0
          ? result.user_reasons
          : [
              "The text contains strong claims without supporting evidence.",
              "It uses emotionally charged or uncertain language.",
              "It discusses a sensitive topic that requires verification.",
              "Online verification evidence was limited or inconclusive.",
            ];

    const guidance =
      result?.explanation?.user_guidance ||
      result?.user_guidance ||
      result?.guidance ||
      (riskBand === "LOW"
        ? "This content appears lower risk, but important claims should still be checked against trusted sources."
        : riskBand === "HIGH"
          ? "This content presents a high misinformation risk. Avoid sharing until key claims have been checked against trusted sources."
          : "This content presents a moderate misinformation risk. Verify important claims using trusted sources before sharing.");

    return {
      misinformationLikelihood,
      modelConfidence,
      riskBand,
      styles,
      manipulationIntensity,
      tone,
      verificationUi,
      verificationConfidence,
      claims,
      triggers,
      propagation,
      whyShare,
      algorithmicAdvantage,
      contentAnalysis,
      reasons,
      guidance,
      verdictLabel: formatVerdict(result?.action_verdict, riskBand),
      raw: result,
    };
  }, [result]);

  if (!derived) return null;

  const {
    misinformationLikelihood,
    modelConfidence,
    riskBand,
    styles,
    manipulationIntensity,
    tone,
    verificationUi,
    verificationConfidence,
    claims,
    triggers,
    propagation,
    whyShare,
    algorithmicAdvantage,
    contentAnalysis,
    reasons,
    guidance,
    verdictLabel,
    raw,
  } = derived;

  const triggerCount = triggers.length;
  const spreadSpeed = propagation?.infection_rate || "Moderate";
  const saturationPoint = propagation?.saturation_point || "Hours to days";
  const audienceReach = propagation?.estimated_audience_reach || "Variable reach";
  const targetDemographic = propagation?.target_demographic || "General audience";

  return (
    <div className="mt-8 space-y-6">
      <div
        className={`relative overflow-hidden rounded-3xl border ${styles.border} bg-gradient-to-br ${styles.gradient} shadow-2xl ${styles.glow}`}
      >
        <div className="absolute inset-0 bg-slate-950/75 backdrop-blur-sm" />
        <div className="relative p-6 md:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex items-start gap-4">
              <div className={`rounded-2xl p-4 shadow-lg ${styles.iconBg}`}>{styles.icon}</div>
              <div>
                <p className="text-sm font-medium uppercase tracking-[0.2em] text-slate-300">
                  Analysis Report
                </p>
                <h2 className="mt-2 text-2xl font-bold text-white md:text-3xl">
                  {riskBand === "LOW"
                    ? "Low-risk signal"
                    : riskBand === "HIGH"
                      ? "High-risk signal"
                      : "Medium-risk signal"}
                </h2>
                <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-100">
                  System verdict: <span className="font-semibold text-white">{verdictLabel}</span>
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setShowDebug((v) => !v)}
              className="inline-flex items-center gap-2 self-start rounded-xl border border-white/15 bg-white/10 px-4 py-2 text-sm font-medium text-slate-100 hover:bg-white/15"
            >
              {showDebug ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              {showDebug ? "Hide Debug" : "Show Debug"}
            </button>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricBox
              label="Misinformation Risk"
              value={riskBand}
              subtext={getRiskExplanation(riskBand, misinformationLikelihood, modelConfidence)}
            />
            <MetricBox
              label="Estimated misinformation likelihood"
              value={`${misinformationLikelihood}%`}
              subtext="This is the model’s estimated chance that the content is misleading or false."
            />
            <MetricBox
              label="Model confidence"
              value={`${modelConfidence}%`}
              subtext="This shows how certain the model is about its risk assessment."
            />
            <MetricBox
              label="Manipulation tactics"
              value={scoreLabel(manipulationIntensity).toUpperCase()}
              subtext={`Intensity ${manipulationIntensity}%. Detected ${triggerCount} engagement cue${
                triggerCount === 1 ? "" : "s"
              }.`}
            />
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <div className="rounded-2xl border border-white/15 bg-slate-800/95 p-4 shadow-sm">
              <div className="flex items-center gap-3">
                <Info className={`h-5 w-5 ${tone.color}`} />
                <p className="text-sm font-semibold text-white">Tone</p>
              </div>
              <p className={`mt-3 text-base font-semibold ${tone.color}`}>{tone.label}</p>
              <p className="mt-2 text-sm text-slate-100">
                This content appears {tone.label.toLowerCase()} in tone.
              </p>
            </div>

            <div className="rounded-2xl border border-white/15 bg-slate-800/95 p-4 shadow-sm">
              <div className="flex items-center gap-3">
                <SearchCheck className={`h-5 w-5 ${verificationUi.color}`} />
                <p className="text-sm font-semibold text-white">Internet Verification</p>
              </div>
              <p className={`mt-3 text-base font-semibold ${verificationUi.color}`}>{verificationUi.label}</p>
              <p className="mt-2 text-sm text-slate-100">{verificationUi.subtext}</p>
              {verificationConfidence !== null ? (
                <p className="mt-2 text-sm text-slate-200">
                  Verification confidence: {verificationConfidence}%
                </p>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      <SectionCard icon={<Brain className="h-5 w-5 text-cyan-200" />} title="Content Analysis">
        <p className="text-sm leading-7 text-white">{contentAnalysis}</p>
      </SectionCard>

      <SectionCard icon={<Info className="h-5 w-5 text-sky-200" />} title="Key reasons for this assessment">
        <div className="space-y-3">
          {reasons.map((reason, index) => (
            <div
              key={`reason-${index}`}
              className="rounded-2xl border border-white/15 bg-slate-800/95 px-4 py-3 text-sm leading-6 text-white shadow-sm"
            >
              {reason}
            </div>
          ))}
        </div>
      </SectionCard>

      <SectionCard icon={<Users className="h-5 w-5 text-violet-200" />} title="Why people might share this">
        <p className="text-sm leading-7 text-white">{whyShare}</p>
        <div className="mt-4 rounded-2xl border border-white/15 bg-slate-800/95 p-4 shadow-sm">
          <p className="text-xs uppercase tracking-wide text-slate-300">Algorithmic interpretation</p>
          <p className="mt-2 text-sm leading-6 text-slate-100">{algorithmicAdvantage}</p>
        </div>
      </SectionCard>

      <SectionCard icon={<TrendingUp className="h-5 w-5 text-amber-200" />} title="How this content could spread">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricBox label="Estimated spread speed" value={spreadSpeed} />
          <MetricBox label="Likely saturation point" value={saturationPoint} />
          <MetricBox label="Potential audience reach" value={audienceReach} />
          <MetricBox label="Likely target audience" value={targetDemographic} />
        </div>
      </SectionCard>

      <SectionCard
        icon={<Network className="h-5 w-5 text-sky-200" />}
        title="Detected engagement signals"
        right={
          <span className="rounded-full bg-white/10 px-3 py-1 text-xs text-slate-100">
            {triggerCount} detected
          </span>
        }
      >
        <div className="space-y-4">
          {triggerCount > 0 ? (
            triggers.map((trigger, index) => (
              <TriggerBar
                key={`trigger-${index}`}
                name={trigger?.name}
                score={trigger?.score}
                explanation={trigger?.explanation}
              />
            ))
          ) : (
            <p className="text-sm text-slate-100">No detailed engagement signals were returned.</p>
          )}
        </div>
      </SectionCard>

      <SectionCard
        icon={<Globe className="h-5 w-5 text-emerald-200" />}
        title="Verified Claims"
        right={
          claims.length > 0 ? (
            <button
              type="button"
              onClick={() => setShowAllClaims((v) => !v)}
              className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/10 px-3 py-2 text-xs text-slate-100 hover:bg-white/15"
            >
              {showAllClaims ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              {showAllClaims ? "Hide Claims" : "Show Claims"}
            </button>
          ) : null
        }
      >
        {claims.length > 0 ? (
          showAllClaims ? (
            <div className="space-y-4">
              {claims.map((claim, index) => (
                <ClaimCard key={`claim-${index}`} claim={claim} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-100">Claims are hidden.</p>
          )
        ) : (
          <p className="text-sm text-slate-100">No claim-level verification results were returned.</p>
        )}
      </SectionCard>

      <SectionCard icon={<BadgeCheck className="h-5 w-5 text-emerald-200" />} title="Recommended Action">
        <div className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${styles.pill}`}>
          {riskBand === "LOW"
            ? "Low-risk signal"
            : riskBand === "HIGH"
              ? "High-risk signal"
              : "Medium-risk signal"}
        </div>

        <p className="mt-4 text-sm leading-7 text-white">{guidance}</p>

        <div className="mt-4">
          <RiskActions
            riskBand={riskBand}
            verdict={raw?.action_verdict}
            showDebug={false}
            debugInfo={{
              raw_prob: misinformationLikelihood,
              adjusted_prob: misinformationLikelihood,
              stance: raw?.misinformation?.stance || "neutral",
              model_breakdown: raw?.model_breakdown || {},
            }}
          />
        </div>
      </SectionCard>

      {showDebug ? (
        <SectionCard icon={<Info className="h-5 w-5 text-slate-200" />} title="Debug Data">
          <pre className="max-h-[500px] overflow-auto rounded-2xl border border-white/15 bg-slate-950/90 p-4 text-xs leading-6 text-slate-100">
            {JSON.stringify(raw, null, 2)}
          </pre>
        </SectionCard>
      ) : null}
    </div>
  );
}