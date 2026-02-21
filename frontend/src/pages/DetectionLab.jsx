// frontend/DetectionLab.jsx
import React, { useState, useEffect } from "react";
import { FileText, Loader2, AlertCircle } from "lucide-react";
import { api } from "../services/api.js";
import ResultCard from "../components/ResultCard.jsx";
import ImageUploader from "../components/ImageUploader.jsx";

// Validation function for saved results
const isValidResult = (result) => {
  return result && 
         typeof result === 'object' && 
         result.action_verdict && 
         result.risk_band &&
         ['SAFE_TO_SHARE', 'VERIFY_REQUIRED', 'LIKELY_MISINFORMATION'].includes(result.action_verdict);
};

export default function DetectionLab() {
  // Load saved state from localStorage on initial render with validation
  const [input, setInput] = useState(() => {
    try {
      return localStorage.getItem('detectionLab_input') || "";
    } catch {
      return "";
    }
  });
  
  const [imageFile, setImageFile] = useState(null);
  const [textAnalyzing, setTextAnalyzing] = useState(false);
  const [imageAnalyzing, setImageAnalyzing] = useState(false);
  
  // Load saved result with validation
  const [result, setResult] = useState(() => {
    try {
      const saved = localStorage.getItem('detectionLab_result');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (isValidResult(parsed)) {
          return parsed;
        }
        // Invalid saved data - clear it
        localStorage.removeItem('detectionLab_result');
      }
    } catch (e) {
      console.warn("Failed to load saved result:", e);
      localStorage.removeItem('detectionLab_result');
    }
    return null;
  });
  
  const [err, setErr] = useState("");

  // Save input to localStorage whenever it changes
  useEffect(() => {
    try {
      localStorage.setItem('detectionLab_input', input);
    } catch (e) {
      console.warn("Failed to save input:", e);
    }
  }, [input]);

  // Save result to localStorage whenever it changes
  useEffect(() => {
    try {
      if (result && isValidResult(result)) {
        localStorage.setItem('detectionLab_result', JSON.stringify(result));
      } else {
        localStorage.removeItem('detectionLab_result');
      }
    } catch (e) {
      console.warn("Failed to save result:", e);
    }
  }, [result]);

  const handleTextAnalysis = async () => {
    if (!input.trim()) return;
    
    setErr("");
    setTextAnalyzing(true);
    setResult(null); // Clear previous result
    
    try {
      // Add timeout to fetch
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout
      
      const res = await api.predictAutoText(input);
      clearTimeout(timeoutId);
      
      if (isValidResult(res)) {
        setResult(res);
      } else {
        throw new Error("Invalid response format from server");
      }
    } catch (e) {
      if (e.name === 'AbortError') {
        setErr("Request timed out. The server might be busy.");
      } else {
        setErr(e?.message || "Analysis failed. Check if backend is running.");
      }
    } finally {
      setTextAnalyzing(false);
    }
  };

  const handleImageAnalysis = async () => {
    if (!imageFile) return;
    
    setErr("");
    setImageAnalyzing(true);
    setResult(null);
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 45000); // 45 second timeout for images
      
      const res = await api.predictAutoImage(imageFile);
      clearTimeout(timeoutId);
      
      if (isValidResult(res)) {
        setResult(res);
      } else {
        throw new Error("Invalid response format from server");
      }
    } catch (e) {
      if (e.name === 'AbortError') {
        setErr("Image analysis timed out. The image might be too large or OCR is slow.");
      } else {
        setErr(e?.message || "Analysis failed. Make sure Tesseract OCR is installed.");
      }
    } finally {
      setImageAnalyzing(false);
    }
  };

  // Clear all saved data
  const handleClear = () => {
    setInput("");
    setImageFile(null);
    setResult(null);
    setErr("");
    try {
      localStorage.removeItem('detectionLab_input');
      localStorage.removeItem('detectionLab_result');
    } catch (e) {
      console.warn("Failed to clear localStorage:", e);
    }
  };

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header with Clear button */}
      <div className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Detection & Analysis Lab</h1>
          <p className="text-gray-600">
            Paste text or upload an image with text to detect misinformation. This uses 3 ensemble models 
            analyzes content and provides early warning signals.
          </p>
        </div>
        {(input || imageFile || result) && (
          <button
            onClick={handleClear}
            className="px-3 py-2 text-sm text-gray-600 hover:text-gray-900 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Clear All
          </button>
        )}
      </div>

      {/* Input Grid */}
      <div className="grid md:grid-cols-2 gap-6 mb-8">
        {/* Text Input */}
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <FileText className="w-5 h-5 text-gray-700" />
            <h2 className="font-semibold text-gray-900">Text Analysis</h2>
          </div>
          
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Paste text here..."
            className="w-full h-32 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none resize-none"
            disabled={textAnalyzing || imageAnalyzing}
          />
          
          <div className="mt-4 flex items-center justify-between">
            <span className="text-xs text-gray-400">
              {input.length} characters
            </span>
            <button
              onClick={handleTextAnalysis}
              disabled={textAnalyzing || imageAnalyzing || !input.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {textAnalyzing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Analyzing...
                </>
              ) : (
                "Analyze Text"
              )}
            </button>
          </div>
        </div>

        {/* Image Upload */}
        <ImageUploader
          onImageSelect={setImageFile}
          onAnalyze={handleImageAnalysis}
          isAnalyzing={imageAnalyzing}
        />
      </div>

      {/* Error Message */}
      {err && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-700 text-sm flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
            <span>{err}</span>
          </p>
        </div>
      )}

      {/* Loading State for Result */}
      {(textAnalyzing || imageAnalyzing) && !result && (
        <div className="mt-8 p-12 bg-white border border-gray-200 rounded-xl text-center">
          <Loader2 className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Analyzing content... This may take a moment.</p>
          {imageAnalyzing && (
            <p className="text-sm text-gray-400 mt-2">
              OCR text extraction in progress...
            </p>
          )}
        </div>
      )}

      {/* Result - Now persists across navigation */}
      {result && !textAnalyzing && !imageAnalyzing && (
        <div className="mt-8">
          <ResultCard result={result} />
        </div>
      )}
    </div>
  );
}