import React from 'react';
import { AlertCircle, Eye, TrendingUp, Info, Shield, Zap, Share2 } from 'lucide-react';

export default function SpreadRiskCard({ earlyData, signals, explanation, text, stance = "neutral" }) {
  if (!earlyData) return null;

  const { prob_pos, model_used, virality_score } = earlyData;
  const probability = (prob_pos * 100).toFixed(1);
  const virality = virality_score ? (virality_score * 100).toFixed(0) : null;

  const getSpreadReasons = (text, stance) => {
    if (!text) return [];
    
    const reasons = [];
    const lowerText = text.toLowerCase();
    
    // Different wording based on stance
    if (stance === "debunking") {
      if (lowerText.includes('urgent') || lowerText.includes('breaking')) {
        reasons.push({
          icon: "⏱️",
          text: "Timely topic that may attract attention"
        });
      }
      
      const healthWords = ['vaccine', 'health', 'study', 'research'];
      const foundHealth = healthWords.filter(word => lowerText.includes(word));
      if (foundHealth.length > 0) {
        reasons.push({
          icon: "📊",
          text: `Health-related topics often generate discussion`
        });
      }
      
      if (lowerText.includes('share') || lowerText.includes('spread')) {
        reasons.push({
          icon: "📢",
          text: "Encourages sharing accurate information"
        });
      }
    } else {
      if (lowerText.includes('urgent') || lowerText.includes('breaking')) {
        reasons.push({
          icon: "⏱️",
          text: "Urgency cues can encourage rapid sharing"
        });
      }
      
      const emotionalWords = ['shocked', 'outrage', 'furious', 'scared'];
      const foundEmotional = emotionalWords.filter(word => lowerText.includes(word));
      if (foundEmotional.length > 0) {
        reasons.push({
          icon: "😮",
          text: "Emotional language tends to increase engagement"
        });
      }
      
      if (lowerText.includes('share') || lowerText.includes('forward')) {
        reasons.push({
          icon: "📢",
          text: "Contains prompts that encourage sharing"
        });
      }
    }
    
    return reasons.slice(0, 2);
  };

  const spreadReasons = getSpreadReasons(text, stance);

  // Different styling based on stance
  const getConfig = () => {
    if (stance === "debunking") {
      return {
        bg: 'bg-blue-50',
        border: 'border-blue-200',
        icon: <Share2 className="w-4 h-4 text-blue-600" />,
        title: 'Spread Potential',
        badge: 'bg-blue-100 text-blue-700',
        message: probability >= 60 
          ? "This fact-check may spread widely - good information reaching many people!"
          : probability >= 30
          ? "This topic has moderate potential to reach interested audiences."
          : "Limited spread expected for this fact-check."
      };
    } else {
      return {
        bg: 'bg-purple-50',
        border: 'border-purple-200',
        icon: <Zap className="w-4 h-4 text-purple-600" />,
        title: 'Virality Risk',
        badge: probability >= 60 ? 'bg-orange-100 text-orange-700' : 
                probability >= 30 ? 'bg-yellow-100 text-yellow-700' : 
                'bg-green-100 text-green-700',
        message: probability >= 60 
          ? "⚠️ High potential to spread rapidly. Verify before sharing."
          : probability >= 30
          ? "👁️ Moderate spread potential. Review carefully."
          : "✓ Low spread potential."
      };
    }
  };

  const config = getConfig();

  return (
    <div className={`mt-4 rounded-lg border ${config.border} ${config.bg} p-4`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-white rounded-full shadow-sm">
            {config.icon}
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-800">{config.title}</h3>
            <p className="text-xs text-gray-500">How this content may spread</p>
          </div>
        </div>
        <span className={`text-xs px-2 py-1 rounded-full font-medium ${config.badge}`}>
          {probability}%
        </span>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="bg-white rounded-lg p-2 border border-gray-100">
          <p className="text-xs text-gray-500">Spread Probability</p>
          <p className="text-base font-semibold text-gray-700">{probability}%</p>
        </div>
        {virality && (
          <div className="bg-white rounded-lg p-2 border border-gray-100">
            <p className="text-xs text-gray-500">Engagement Score</p>
            <p className="text-base font-semibold text-gray-700">{virality}%</p>
          </div>
        )}
      </div>

      {/* Progress Bar */}
      <div className="mb-3">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-gray-500">Spread likelihood</span>
          <span className={`font-medium ${stance === "debunking" ? 'text-blue-600' : 'text-purple-600'}`}>
            {probability}%
          </span>
        </div>
        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div 
            className={`h-full ${stance === "debunking" ? 'bg-blue-500' : 'bg-purple-500'}`}
            style={{ width: `${probability}%` }}
          />
        </div>
      </div>

      {/* Why This Might Spread */}
      {spreadReasons.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-200">
          <div className="flex items-center gap-1 mb-2">
            <Info className="w-3.5 h-3.5 text-gray-500" />
            <span className="text-xs font-medium text-gray-700">Why this might spread:</span>
          </div>
          <div className="space-y-2">
            {spreadReasons.map((reason, index) => (
              <div key={index} className="flex items-start gap-2 text-xs bg-white/50 p-2 rounded">
                <span className="text-base">{reason.icon}</span>
                <span className="text-gray-700">{reason.text}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Status Message */}
      <div className={`mt-3 flex items-center gap-1 text-xs p-2 rounded border ${
        stance === "debunking" 
          ? 'bg-blue-50 border-blue-200 text-blue-700' 
          : probability >= 60 
            ? 'bg-orange-50 border-orange-200 text-orange-700'
            : 'bg-gray-50 border-gray-200 text-gray-700'
      }`}>
        {config.icon}
        <span>{config.message}</span>
      </div>

      {/* Model Info (optional) */}
      <p className="text-xs text-gray-400 mt-2 italic">
        Based on language patterns and engagement cues
      </p>
    </div>
  );
}