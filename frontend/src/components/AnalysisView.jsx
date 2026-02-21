import React, { useState } from "react";
import ResultCard from "../components/ResultCard.jsx";
import { api } from "../services/api.js";
import { Upload, RefreshCw, Activity, FileText, Image, Sparkles } from "lucide-react";

export default function AnalysisView() {
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [err, setErr] = useState("");

  async function runText() {
    setErr("");
    setLoading(true);
    setResult(null);
    try {
      const r = await api.predictAutoText(text);
      setResult(r);
    } catch (e) {
      setErr(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  async function runImage() {
    setErr("");
    setLoading(true);
    setResult(null);
    try {
      const r = await api.predictAutoImage(file);
      setResult(r);
    } catch (e) {
      setErr(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-3 rounded-2xl bg-white/5 border border-white/10">
          <Sparkles className="w-6 h-6 text-white/80" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-white">Detection & Analysis Lab</h1>
          <p className="text-sm text-white/60">
            Paste a post or upload a screenshot. The system returns a rumour-risk verdict, explanation, and early-detection signal.
          </p>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Text input */}
        <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
          <div className="flex items-center gap-2 mb-3">
            <FileText className="w-4 h-4 text-white/70" />
            <h2 className="text-white font-medium">Source Material</h2>
          </div>

          <textarea
            className="w-full min-h-[170px] rounded-xl bg-black/20 border border-white/10 p-3 text-white placeholder:text-white/40 focus:outline-none focus:ring-2 focus:ring-white/20"
            placeholder="Paste a post here..."
            value={text}
            onChange={(e) => setText(e.target.value)}
          />

          <div className="mt-4 flex gap-3">
            <button
              onClick={runText}
              disabled={loading || !text.trim()}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white text-black font-medium disabled:opacity-50"
            >
              {loading ? <Activity className="w-4 h-4 animate-pulse" /> : <RefreshCw className="w-4 h-4" />}
              Analyse Text
            </button>
          </div>
        </div>

        {/* Image upload */}
        <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
          <div className="flex items-center gap-2 mb-3">
            <Image className="w-4 h-4 text-white/70" />
            <h2 className="text-white font-medium">Screenshot (OCR)</h2>
          </div>

          <label className="block w-full rounded-xl border border-dashed border-white/20 bg-black/10 p-6 text-center cursor-pointer hover:bg-white/5 transition">
            <input
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            <div className="flex flex-col items-center gap-2">
              <Upload className="w-6 h-6 text-white/70" />
              <div className="text-sm text-white/70">
                Click to upload or drag and drop
              </div>
              <div className="text-xs text-white/40">PNG, JPG, GIF up to 10MB</div>
              {file ? <div className="text-xs text-white/70 mt-2">{file.name}</div> : null}
            </div>
          </label>

          <div className="mt-4 flex gap-3">
            <button
              onClick={runImage}
              disabled={loading || !file}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white text-black font-medium disabled:opacity-50"
            >
              {loading ? <Activity className="w-4 h-4 animate-pulse" /> : <RefreshCw className="w-4 h-4" />}
              Analyse Image
            </button>
          </div>
        </div>
      </div>

      {err ? (
        <div className="mt-6 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-200 text-sm whitespace-pre-wrap">
          {err}
        </div>
      ) : null}

      {result ? (
        <div className="mt-6">
          <ResultCard result={result} />
        </div>
      ) : null}
    </div>
  );
}
