import React, { useMemo, useState } from "react";
import { 
  AlertCircle, 
  CheckCircle, 
  AlertTriangle, 
  Info, 
  Shield, 
  TrendingUp, 
  Zap, 
  Brain, 
  Share2, 
  Eye, 
  Scale,
  Code,
  HelpCircle,
  FileText,
  Globe,
  Clock,
  Award,
  Sparkles,
  Newspaper,
  Quote
} from "lucide-react";
import RiskActions from "./RiskActions.jsx";

function getRiskStyles(band) {
  const b = (band || "MEDIUM").toUpperCase();

  if (b === "LOW") {
    return {
      border: "border-green-200",
      bg: "bg-green-50",
      text: "text-green-700",
      icon: <CheckCircle className="w-5 h-5 text-green-600" />,
      badge: "bg-green-100 text-green-700 border-green-200",
      progress: "bg-green-500",
      lightBg: "bg-green-50/50",
      gradient: "from-green-500 to-green-600",
      hover: "hover:bg-green-100",
      displayText: "LOW"
    };
  }

  if (b === "HIGH") {
    return {
      border: "border-red-200",
      bg: "bg-red-50",
      text: "text-red-700",
      icon: <AlertCircle className="w-5 h-5 text-red-600" />,
      badge: "bg-red-100 text-red-700 border-red-200",
      progress: "bg-red-500",
      lightBg: "bg-red-50/50",
      gradient: "from-red-500 to-red-600",
      hover: "hover:bg-red-100",
      displayText: "HIGH"
    };
  }

  return {
    border: "border-yellow-200",
    bg: "bg-yellow-50",
    text: "text-yellow-700",
    icon: <AlertTriangle className="w-5 h-5 text-yellow-600" />,
    badge: "bg-yellow-100 text-yellow-700 border-yellow-200",
    progress: "bg-yellow-500",
    lightBg: "bg-yellow-50/50",
    gradient: "from-yellow-500 to-yellow-600",
    hover: "hover:bg-yellow-100",
    displayText: "MEDIUM"
  };
}

// Helper function to get early warning style based on content type
const getEarlyWarningStyle = (score, isDebunking) => {
  const percent = Math.round(score * 100);
  
  if (isDebunking) {
    if (percent >= 50) {
      return {
        bg: "bg-green-100",
        text: "text-green-700",
        icon: <CheckCircle className="w-4 h-4 text-green-600" />,
        label: "High Visibility",
        message: "This fact-check is gaining traction - good information is spreading!"
      };
    } else if (percent >= 25) {
      return {
        bg: "bg-blue-100",
        text: "text-blue-700",
        icon: <Info className="w-4 h-4 text-blue-600" />,
        label: "Moderate Visibility",
        message: "This fact-check is reaching some audiences."
      };
    } else {
      return {
        bg: "bg-gray-100",
        text: "text-gray-700",
        icon: <Eye className="w-4 h-4 text-gray-600" />,
        label: "Low Visibility",
        message: "This fact-check has limited reach so far."
      };
    }
  } else {
    if (percent >= 50) {
      return {
        bg: "bg-orange-100",
        text: "text-orange-700",
        icon: <AlertCircle className="w-4 h-4 text-orange-600" />,
        label: "High Virality Risk",
        message: "⚠️ This content shows strong patterns of going viral. Be cautious."
      };
    } else if (percent >= 25) {
      return {
        bg: "bg-yellow-100",
        text: "text-yellow-700",
        icon: <Zap className="w-4 h-4 text-yellow-600" />,
        label: "Moderate Virality Risk",
        message: "👁️ This content has moderate potential to spread."
      };
    } else {
      return {
        bg: "bg-green-100",
        text: "text-green-700",
        icon: <CheckCircle className="w-4 h-4 text-green-600" />,
        label: "Low Virality Risk",
        message: "✓ Low spread potential. Content appears typical."
      };
    }
  }
};

// Helper to format timestamp into relative time (e.g., "2 hours ago") or absolute time if older than a day
const formatTimestamp = (timestamp) => {
  if (!timestamp) return "";
  try {
    const date = new Date(timestamp);
    const now = new Date();
    const diffHours = Math.floor((now - date) / (1000 * 60 * 60));
    
    if (diffHours < 1) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else if (diffHours < 24) {
      return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    } else {
      const diffDays = Math.floor(diffHours / 24);
      return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    }
  } catch {
    return "";
  }
};

export default function ResultCard({ result }) {
  const [debugMode, setDebugMode] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  
  // Extract scores with defaults
  const misinformation = result?.misinformation || { 
    band: "MEDIUM", 
    probability: 0.5,
    raw_probability: 0.5,
    stance: "neutral",
    explanation: ""
  };
  
  const tactics = result?.manipulation_tactics || { 
    band: "MEDIUM", 
    intensity: 0.5, 
    detected_triggers: []
  };
  
  const misinfoStyles = useMemo(() => getRiskStyles(misinformation.band), [misinformation.band]);
  const tacticsStyles = useMemo(() => getRiskStyles(tactics.band), [tactics.band]);

  const analyst = result?.analyst;
  const explanation = result?.explanation;
  const modelBreakdown = result?.model_breakdown;
  const earlyData = result?.early;
  const originalText = result?.extracted_text || result?.explanation?.signals?.original_text || "";
  
  // Get triggers from either analyst or explanation
  const triggers = analyst?.triggers || explanation?.triggers || [];
  
  // Get key phrases from explanation
  const keyPhrases = explanation?.key_phrases || [];
  
  const stanceDisplay = {
    debunking: { text: "Fact-Checking", icon: "⚖️", color: "text-blue-600 bg-blue-100", description: "This content is fact-checking or educational" },
    warning: { text: "Verification Advice", icon: "⚠️", color: "text-yellow-600 bg-yellow-100", description: "This content warns about misinformation" },
    spreading: { text: "Unverified Claims", icon: "📢", color: "text-orange-600 bg-orange-100", description: "This content may be spreading unverified claims" },
    neutral: { text: "Neutral", icon: "📄", color: "text-gray-600 bg-gray-100", description: "This content appears neutral in tone" },
    satire: { text: "Satire/Parody", icon: "🎭", color: "text-purple-600 bg-purple-100", description: "This content is satirical or humorous" },
    credible: { text: "Credible News", icon: "📰", color: "text-green-600 bg-green-100", description: "This content cites official sources" }
  }[misinformation.stance] || { text: "Neutral", icon: "📄", color: "text-gray-600 bg-gray-100", description: "" };

  // Get early warning style
  const earlyWarningStyle = earlyData ? getEarlyWarningStyle(
    earlyData.prob_pos, 
    misinformation.stance === "debunking"
  ) : null;

  // Prepare debug info for RiskActions
  const debugInfo = {
    raw_prob: Math.round((misinformation.raw_probability || 0.5) * 100),
    adjusted_prob: Math.round(misinformation.probability * 100),
    debunk_score: misinformation.stance === "debunking" ? 85 : 
                  misinformation.stance === "spreading" ? 10 : 50,
    stance: misinformation.stance,
    model_breakdown: modelBreakdown ? {
      unified: Math.round((modelBreakdown.unified || 0) * 100),
      enhanced: modelBreakdown.enhanced ? Math.round(modelBreakdown.enhanced * 100) : null,
      legacy: modelBreakdown.legacy ? Math.round(modelBreakdown.legacy * 100) : null,
    } : null
  };

  // Format timestamp
  const formattedTime = result?.timestamp ? formatTimestamp(result.timestamp) : "";

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-lg">
      {/* Header with Debug Toggle and Help */}
      <div className="p-6 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-white">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Scale className="w-5 h-5 text-gray-500" />
            <h2 className="text-xl font-semibold text-gray-900">Analysis Report</h2>
            <button
              onClick={() => setShowHelp(!showHelp)}
              className="p-1 rounded-full hover:bg-gray-200 transition-colors"
              title="How to read this report"
            >
              <HelpCircle className="w-4 h-4 text-gray-400" />
            </button>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setDebugMode(!debugMode)}
              className={`p-2 rounded-lg transition-colors ${
                debugMode ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
              }`}
              title={debugMode ? "Hide technical details" : "Show technical details (research mode)"}
            >
              <Code className="w-4 h-4" />
            </button>
            <span className={`px-3 py-1 rounded-full text-xs font-medium border ${stanceDisplay.color}`}>
              {stanceDisplay.icon} {stanceDisplay.text}
            </span>
          </div>
        </div>
        
        {/* Help Tooltip */}
        {showHelp && (
          <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700">
            <p className="font-medium mb-1">📊 How to read this report:</p>
            <ul className="list-disc list-inside space-y-1">
              <li><span className="font-medium">Misinformation Risk:</span> How likely this content is to be false/misleading</li>
              <li><span className="font-medium">Analysis Confidence:</span> Overall confidence in the analysis</li>
              <li><span className="font-medium">Key Phrases:</span> Actual words that influenced the analysis</li>
              <li><span className="font-medium">What Triggered This Analysis:</span> Specific patterns detected with percentages</li>
            </ul>
          </div>
        )}
        
        {/* Two-Box Display - MINIMAL */}
        <div className="grid grid-cols-2 gap-4">
          {/* Risk Box - UPDATED with proper label */}
          <div className={`${misinfoStyles.bg} border ${misinfoStyles.border} rounded-lg p-4`}>
            <div className="flex items-center gap-2 mb-2">
              {misinfoStyles.icon}
              <span className="text-sm font-medium text-gray-700">Risk Level of Misinformation</span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className={`text-3xl font-bold ${misinfoStyles.text}`}>{misinfoStyles.displayText}</span>
              <span className="text-sm text-gray-500">{Math.round(misinformation.probability * 100)}%</span>
            </div>
            <p className="text-xs text-gray-500 mt-2">{stanceDisplay.text}</p>
          </div>
          
          {/* Patterns Box */}
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <Brain className="w-5 h-5 text-gray-600" />
              <span className="text-sm font-medium text-gray-700">Signals</span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="text-3xl font-bold text-gray-900">{triggers.length}</span>
              <span className="text-sm text-gray-500">detected</span>
            </div>
            {triggers.length > 0 && (
              <p className="text-xs text-gray-500 mt-2 truncate" title={triggers.map(t => t.name).join(', ')}>
                {triggers.slice(0,2).map(t => t.name).join(', ')}
                {triggers.length > 2 ? ' + more' : ''}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-6 space-y-6">
        {/* Explanation from Backend */}
        {explanation?.user_summary && (
          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-6">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-blue-100 rounded-lg">
                <FileText className="w-6 h-6 text-blue-600" />
              </div>
              <div className="flex-1">
                <h3 className="text-base font-semibold text-gray-800 mb-3">
                  {misinformation.stance === "debunking" ? "🔍 Fact-Checking Content Detected" :
                   misinformation.stance === "spreading" ? "🚨 High-Risk Content Detected" :
                   "📄 Content Analysis"}
                </h3>
                <p className="text-base text-gray-700 leading-relaxed whitespace-pre-line">
                  {explanation.user_summary}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Key Phrases That Influenced Analysis */}
        {keyPhrases.length > 0 && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <Quote className="w-4 h-4 text-blue-600" />
              <h3 className="text-sm font-medium text-gray-700">Key Phrases That Influenced This Analysis</h3>
            </div>
            <div className="flex flex-wrap gap-2">
              {keyPhrases.map((phrase, idx) => (
                <div key={idx} className="bg-white border border-blue-200 rounded-lg px-3 py-2 shadow-sm">
                  <span className="text-sm font-medium text-blue-700">"{phrase.phrase}"</span>
                  <span className="text-xs text-blue-500 ml-2">{Math.round(phrase.score * 100)}%</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Risk Actions with Debug Mode */}
        <RiskActions 
          riskBand={misinformation.band}
          verdict={result?.action_verdict}
          showDebug={debugMode}
          debugInfo={debugInfo}
        />

        {/* Virality Potential Section */}
        {earlyData && earlyWarningStyle && (
          <div className={`${earlyWarningStyle.bg} border border-gray-200 rounded-lg p-4`}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                {earlyWarningStyle.icon}
                <span className="text-sm font-medium text-gray-700">Virality Potential</span>
              </div>
              <span className={`text-xs px-2 py-1 rounded-full font-medium ${earlyWarningStyle.bg} ${earlyWarningStyle.text}`}>
                {earlyWarningStyle.label}
              </span>
            </div>
            
            <p className="text-xs text-gray-700">
              {earlyWarningStyle.message}
            </p>
            
            {/* Progress bar */}
            <div className="mt-3">
              <div className="flex justify-between text-xs mb-1">
                <span className="text-gray-500">Spread potential</span>
                <span className={`font-medium ${earlyWarningStyle.text}`}>{Math.round(earlyData.prob_pos * 100)}%</span>
              </div>
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div 
                  className={`h-full ${
                    misinformation.stance === "debunking" ? 'bg-blue-500' :
                    earlyData.prob_pos > 0.5 ? 'bg-orange-500' :
                    earlyData.prob_pos > 0.25 ? 'bg-yellow-500' : 'bg-green-500'
                  }`}
                  style={{ width: `${earlyData.prob_pos * 100}%` }}
                />
              </div>
            </div>
          </div>
        )}

        {/* What Triggered This Analysis - Using triggers from backend */}
        {triggers.length > 0 && (
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
              <Brain className="w-4 h-4" />
              What Triggered This Analysis
            </h3>
            <p className="text-xs text-gray-500 mb-2">Specific language patterns detected in this content</p>
            <div className="space-y-3">
              {triggers.slice(0, 3).map((t, i) => (
                <div key={i} className="bg-gray-50 rounded-lg p-4 border border-gray-100 hover:shadow-sm transition-shadow">
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-gray-700">{t.name}</span>
                    <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                      t.score > 0.6 ? 'bg-red-100 text-red-700' :
                      t.score > 0.3 ? 'bg-yellow-100 text-yellow-700' :
                      'bg-green-100 text-green-700'
                    }`}>
                      {Math.round(t.score * 100)}% confidence
                    </span>
                  </div>
                  <p className="text-xs text-gray-600 leading-relaxed">{t.explanation}</p>
                  
                  {/* Progress bar for trigger intensity */}
                  <div className="mt-2 h-1 bg-gray-200 rounded-full overflow-hidden">
                    <div 
                      className={`h-full ${
                        t.score > 0.6 ? 'bg-red-500' :
                        t.score > 0.3 ? 'bg-yellow-500' :
                        'bg-green-500'
                      }`}
                      style={{ width: `${t.score * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* How It Could Spread */}
        {analyst?.propagation_dynamics && (
          <div>
            <h3 className="text-sm font-medium text-gray-700 mb-3 flex items-center gap-2">
              <TrendingUp className="w-4 h-4" />
              How It Could Spread
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-gray-50 rounded-lg p-4 border border-gray-100">
                <div className="flex items-center gap-2 mb-2">
                  <Zap className="w-4 h-4 text-yellow-500" />
                  <p className="text-xs text-gray-500">Spread Speed</p>
                </div>
                <p className="text-sm font-medium text-gray-700">
                  {analyst.propagation_dynamics.infection_rate || "Moderate"}
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  How quickly this could circulate
                </p>
              </div>
              <div className="bg-gray-50 rounded-lg p-4 border border-gray-100">
                <div className="flex items-center gap-2 mb-2">
                  <Globe className="w-4 h-4 text-blue-500" />
                  <p className="text-xs text-gray-500">Potential Reach</p>
                </div>
                <p className="text-sm font-medium text-gray-700">
                  {analyst.propagation_dynamics.estimated_audience_reach || "Wide potential reach"}
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  How many people could be exposed
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Insights */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {analyst?.human_susceptibility_logic && (
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 hover:shadow-sm transition-shadow">
              <div className="flex items-center gap-2 mb-2">
                <Brain className="w-4 h-4 text-purple-600" />
                <p className="text-xs font-medium text-purple-700">Why People Might Engage</p>
              </div>
              <p className="text-sm text-purple-900 leading-relaxed">
                {analyst.human_susceptibility_logic}
              </p>
            </div>
          )}

          {analyst?.algorithmic_advantage && (
            <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4 hover:shadow-sm transition-shadow">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-4 h-4 text-indigo-600" />
                <p className="text-xs font-medium text-indigo-700">How AI Detected This</p>
              </div>
              <p className="text-sm text-indigo-900 leading-relaxed">
                {analyst.algorithmic_advantage}
              </p>
            </div>
          )}
        </div>

        {/* Disclaimer */}
        {analyst?.note && (
          <div className="text-xs text-gray-400 italic border-t border-gray-100 pt-4">
            {analyst.note}
          </div>
        )}

        {/* Original Text (collapsed) */}
        {originalText && (
          <details className="text-xs text-gray-400 border-t border-gray-100 pt-2">
            <summary className="cursor-pointer hover:text-gray-600">Show original text</summary>
            <p className="mt-2 p-2 bg-gray-50 rounded">{originalText}</p>
          </details>
        )}

        {/* Timestamp if available - UPDATED formatting */}
        {result?.request_id && (
          <div className="text-xs text-gray-300 text-right flex items-center justify-end gap-1">
            <Clock className="w-3 h-3" />
            {formattedTime && <span>{formattedTime} • </span>}
            Analysis ID: {result.request_id.substring(0, 8)}...
          </div>
        )}
      </div>
    </div>
  );
}