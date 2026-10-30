/*
 * The home page (/). Before a check: headline, input box and "how it works".
 * During and after: the live results (ResultView), or an error message.
 */
import { AlertCircle, RotateCcw } from "lucide-react";
import InputPanel from "../components/InputPanel.jsx";
import ResultView from "../components/ResultView.jsx";
import { useAnalysis } from "../lib/useAnalysis.js";

export default function Check() {
  const a = useAnalysis();
  const started = a.status !== "idle";

  if (!started) {
    return (
      <div className="mx-auto max-w-3xl pt-10 sm:pt-16">
        <h1 className="font-serif text-[2.6rem] font-[650] leading-[1.08] tracking-[-0.02em] text-ink sm:text-[3.4rem] text-balance">
          Check what's true before you share it.
        </h1>
        <p className="mt-4 max-w-[54ch] text-lg leading-relaxed text-ink-soft">
          Paste a post, a link or a screenshot. We pull out each factual claim, look for evidence from fact-checkers and
          reliable sources, and show you which parts hold up.
        </p>
        <div className="mt-8">
          <InputPanel onSubmit={a.run} busy={false} />
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
    ["Find the claims", "Separates checkable facts from opinion, jokes and calls to action."],
    ["Gather evidence", "Searches published fact-checks, reference works and reliable outlets for each claim."],
    ["Weigh it", "Judges each claim against the evidence and links every source so you can check for yourself."],
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
