import React, { useState } from "react";
import { Activity, FileText, Image as ImageIcon, RefreshCw, Upload, XCircle } from "lucide-react";
import ResultCard from "../components/ResultCard.jsx";
import { api } from "../services/api";

export default function AnalysisView() {
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [err, setErr] = useState("");

  const runText = async () => {
    if (!text.trim()) return;
    setLoading(true);
    setErr("");
    try {
      const res = await api.predictAutoText(text, true);
      setResult(res);
    } catch (e) {
      setErr(e?.message || "Text analysis failed.");
    } finally {
      setLoading(false);
    }
  };

  const runImage = async () => {
    if (!file) return;
    setLoading(true);
    setErr("");
    try {
      const res = await api.predictAutoImage(file, true);
      setResult(res);
    } catch (e) {
      setErr(e?.message || "Image analysis failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
        <p className="text-sm text-white/70">
          Analyse text or image-based content for potential misinformation. This system uses an
          ensemble of three models to assess content and provide early warning signals.
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
          <div className="flex items-center gap-2 mb-3">
            <FileText className="w-4 h-4 text-white/70" />
            <h2 className="text-white font-medium">Text Analysis</h2>
          </div>

          <textarea
            className="w-full min-h-[170px] rounded-xl bg-black/20 border border-white/10 p-3 text-white placeholder:text-white/40 focus:outline-none focus:ring-2 focus:ring-white/20"
            placeholder="Paste a post here..."
            value={text}
            onChange={(e) => setText(e.target.value)}
          />

          <div className="mt-4 flex items-center justify-between">
            <span className="text-xs text-white/40">{text.length} characters</span>
            <button
              onClick={runText}
              disabled={loading || !text.trim()}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white text-black font-medium disabled:opacity-50 hover:bg-white/90 transition"
            >
              {loading ? <Activity className="w-4 h-4 animate-pulse" /> : <RefreshCw className="w-4 h-4" />}
              Analyse Text
            </button>
          </div>
        </div>

        <div className="rounded-2xl bg-white/5 border border-white/10 p-5">
          <div className="flex items-center gap-2 mb-3">
            <ImageIcon className="w-4 h-4 text-white/70" />
            <h2 className="text-white font-medium">Image Analysis (OCR)</h2>
          </div>

          {!file ? (
            <label className="block w-full rounded-xl border border-dashed border-white/20 bg-black/10 p-6 text-center cursor-pointer hover:bg-white/5 transition">
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
              <div className="flex flex-col items-center gap-2">
                <Upload className="w-6 h-6 text-white/70" />
                <div className="text-sm text-white/70">Click to upload or drag and drop</div>
                <div className="text-xs text-white/40">PNG, JPG, GIF up to 10MB</div>
              </div>
            </label>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 rounded-xl bg-black/20 border border-white/10">
                <span className="text-sm text-white/70 truncate flex-1">{file.name}</span>
                <button
                  onClick={() => setFile(null)}
                  className="ml-2 p-1 hover:bg-white/10 rounded-full transition"
                >
                  <XCircle className="w-4 h-4 text-white/50" />
                </button>
              </div>
              <button
                onClick={runImage}
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-xl bg-white text-black font-medium disabled:opacity-50 hover:bg-white/90 transition"
              >
                {loading ? (
                  <>
                    <Activity className="w-4 h-4 animate-pulse" />
                    Processing...
                  </>
                ) : (
                  <>
                    <ImageIcon className="w-4 h-4" />
                    Analyse Image
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      </div>

      {err ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{err}</div>
      ) : null}

      {result ? <ResultCard result={result} /> : null}
    </div>
  );
}