/*
 * The home page (/). Before a check: headline, input box and "how it works".
 * During and after: the live results (ResultView), or an error message.
 */
import { AlertCircle, RotateCcw } from "lucide-react";
import InputPanel from "../components/InputPanel.jsx";
import ResultView from "../components/ResultView.jsx";
import { useLocation } from "react-router-dom";
import { useAnalysis } from "../lib/useAnalysis.js";

export default function Check() {
  const a = useAnalysis();
  const location = useLocation(); // the Live page can send a post here to be checked
  const started = a.status !== "idle";

  if (!started) {
    return (
      <div className="mx-auto max-w-3xl pt-10 sm:pt-16">
        <h1 className="font-serif text-[2.6rem] font-[650] leading-[1.08] tracking-[-0.02em] text-ink sm:text-[3.4rem] text-balance">
          Check what's true before you share it.
        </h1>
        <p className="mt-4 max-w-[54ch] text-lg leading-relaxed text-ink-soft">
          Paste a post, a link or a screenshot. MisInfo AI picks out the facts it states, looks them up in fact-checks
          and trusted sources, and shows you which parts are true.
        </p>
        <div className="mt-8">
          <InputPanel onSubmit={a.run} busy={false} initialText={location.state?.text || ""} />
        </div>
        <HowItWorks />
      </div>
    );
  }

  return (
    <div className="pt-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-serif text-2xl font-[650] text-ink">
          {a.status === "running" ? "Checking…" : a.status === "error" ? "The check didn't finish" : "Results"}
        </h1>
        <button
          type="button"
          onClick={a.reset}
          className="inline-flex items-center gap-2 rounded-lg border border-rule bg-sheet px-4 py-2 text-sm font-medium text-ink hover:border-ink-faint"
        >
          <RotateCcw size={15} /> {a.status === "running" ? "Stop and start over" : "Check something else"}
        </button>
      </div>

      {a.status === "error" && (
        <div role="alert" className="mb-6 flex items-start gap-3 rounded-lg border border-refuted/30 bg-refuted-wash px-4 py-3 text-sm text-refuted">
          <AlertCircle size={18} className="mt-0.5 shrink-0" />
          <div>
            <p className="font-medium">{a.error}</p>
            <button type="button" onClick={a.reset} className="mt-1 underline">
              Edit and try again
            </button>
          </div>
        </div>
      )}

      {(a.status !== "error" || a.claims.length > 0) && <ResultView a={a} />}
    </div>
  );
}

function HowItWorks() {
  const steps = [
    ["Find the facts", "Picks out statements that can be checked, and skips opinions and jokes."],
    ["Look them up", "Searches fact-checking websites, encyclopedias and trusted news for each one."],
    ["Show the answer", "Marks each one true, false or unclear, with links so you can see for yourself."],
  ];
  return (
    <ol className="mt-14 grid gap-8 border-t border-rule pt-8 sm:grid-cols-3">
      {steps.map(([t, d], i) => (
        <li key={t}>
          <span className="font-serif text-2xl text-ink-faint">{i + 1}</span>
          <h2 className="mt-1 font-medium text-ink">{t}</h2>
          <p className="mt-1 text-sm leading-relaxed text-ink-soft">{d}</p>
        </li>
      ))}
    </ol>
  );
}
