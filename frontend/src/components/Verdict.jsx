/*
 * The top-right of a result: the progress steps, the overall verdict badge,
 * headline, summary, risk bar, "how sure the check is" dots, guidance and warnings.
 */
import { AlertTriangle, Check, Loader2 } from "lucide-react";
import { OVERALL, confidenceWord, pct } from "../lib/verdicts.js";

const STAGES = [
  { id: "claims", label: "Find the facts" },
  { id: "verify", label: "Look them up" },
  { id: "summary", label: "Give the answer" },
];

export function StageStrip({ stages, done }) {
  return (
    <ol className="flex flex-wrap items-center gap-x-2 gap-y-2 text-sm text-ink-soft" aria-label="Progress">
      {STAGES.map((st, i) => {
        const s = stages[st.id]?.status;
        const finished = done || s === "done" || s === "skipped";
        const running = !done && s === "running";
        return (
          <li key={st.id} className="flex items-center gap-2 whitespace-nowrap">
            <span
              className={`grid h-6 w-6 place-items-center rounded-full border text-xs font-medium ${
                finished ? "border-ink bg-ink text-paper" : running ? "border-cobalt text-cobalt" : "border-rule text-ink-faint"
              }`}
            >
              {finished ? <Check size={13} strokeWidth={3} /> : running ? <Loader2 size={13} className="animate-spin" /> : i + 1}
            </span>
            <span className={running ? "text-ink" : finished ? "text-ink-soft" : "text-ink-faint"}>
              {running && stages[st.id]?.detail ? stages[st.id].detail : st.label}
            </span>
            {i < STAGES.length - 1 && <span className="mx-1 hidden h-px w-6 bg-rule sm:block" aria-hidden />}
          </li>
        );
      })}
    </ol>
  );
}

function Scale({ label, value, hint, tone }) {
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="text-ink-soft">{label}</span>
        <span className="font-medium text-ink">{hint}</span>
      </div>
      <div className="relative mt-2 h-2 rounded-full bg-gradient-to-r from-supported via-mixed to-refuted opacity-90">
        <span
          className="absolute top-1/2 h-4 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-sm bg-ink ring-2 ring-sheet"
          style={{ left: `${Math.max(2, Math.min(98, value * 100))}%` }}
          aria-hidden
        />
      </div>
      {tone && <div className="mt-1 flex justify-between text-xs text-ink-faint"><span>Trustworthy</span><span>Misleading</span></div>}
    </div>
  );
}

function ConfidenceDots({ value }) {
  const filled = Math.round(value * 5);
  return (
    <div className="flex items-baseline justify-between text-sm">
      <span className="text-ink-soft">How sure the check is</span>
      <span className="flex items-center gap-2 font-medium text-ink">
        <span className="flex gap-1" aria-hidden>
          {[0, 1, 2, 3, 4].map((i) => (
            <span key={i} className={`h-2 w-2 rounded-full ${i < filled ? "bg-ink" : "bg-rule"}`} />
          ))}
        </span>
        {confidenceWord(value)}
      </span>
    </div>
  );
}

export function VerdictPanel({ result }) {
  const o = OVERALL[result.overall];
  return (
    <section aria-live="polite" className="verdict-reveal">
      <p className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium ${o.tone.bg} ${o.tone.text}`}>
        <span className={`h-2 w-2 rounded-full ${o.tone.bar}`} />
        {o.label}
      </p>
      <h2 className="mt-3 font-serif text-[1.9rem] font-[650] leading-[1.18] tracking-[-0.01em] text-ink text-balance">
        {result.headline}
      </h2>
      <p className="mt-3 max-w-measure text-[0.98rem] leading-relaxed text-ink-soft">{result.summary}</p>

      <div className="mt-6 space-y-4 border-t border-rule pt-5">
        <Scale label="How likely this is to mislead" value={result.risk} hint={pct(result.risk)} tone />
        <ConfidenceDots value={result.confidence} />
      </div>

      <p className="mt-5 border-l-2 border-ink pl-3 text-[0.95rem] leading-relaxed text-ink">{result.guidance}</p>

      {result.pipeline.warnings.length > 0 && (
        <ul className="mt-4 space-y-1.5">
          {result.pipeline.warnings.map((w) => (
            <li key={w} className="flex gap-2 text-sm text-mixed">
              <AlertTriangle size={15} className="mt-0.5 shrink-0" /> {w}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
