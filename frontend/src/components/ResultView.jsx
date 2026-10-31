/*
 * The whole result layout: annotated text on the left (sticky while you scroll on
 * wide screens), verdict + claims + tactics on the right. It's used both for a
 * live check and for a saved one.
 *
 * `a` is the state from useAnalysis(). Everything here just draws it.
 */
import { Link2, Share2 } from "lucide-react";
import { useState } from "react";
import AnnotatedText from "./AnnotatedText.jsx";
import ClaimNotes from "./ClaimNotes.jsx";
import { StageStrip, VerdictPanel } from "./Verdict.jsx";
import WritingSignals from "./WritingSignals.jsx";
import { sourceName } from "../lib/verdicts.js";

export default function ResultView({ a }) {
  const [active, setActive] = useState(null);
  const [showTactics, setShowTactics] = useState(true);
  const [copied, setCopied] = useState(false);
  const r = a.result;

  const select = (id, scrollDoc) => {
    setActive(id);
    if (scrollDoc) document.querySelector(`[data-claim="${id}"]`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const share = async () => {
    const link = `${location.origin}/a/${r.id}`;
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      prompt("Copy this link", link);
    }
  };

  const noSpans = a.claims.length > 0 && a.claims.every((c) => !c.span);

  return (
    <div className="grid gap-x-12 gap-y-8 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
      {/* Left: the annotated document */}
      <div className="min-w-0 lg:sticky lg:top-20 lg:self-start">
        <div className="mb-4 flex min-h-8 flex-wrap items-center justify-between gap-3">
          <StageStrip stages={a.stages} done={a.status === "done"} />
          {r && (
            <button type="button" onClick={share} className="inline-flex items-center gap-1.5 text-sm text-ink-soft hover:text-ink">
              <Share2 size={15} /> {copied ? "Link copied" : "Copy link"}
            </button>
          )}
        </div>
        <article className="rounded-xl border border-rule bg-sheet px-6 py-6 sm:px-9 sm:py-8 lg:max-h-[calc(100vh-11rem)] lg:overflow-y-auto">
          {r?.source_url && (
            <a href={r.source_url} target="_blank" rel="noopener noreferrer" className="mb-4 flex items-center gap-1.5 truncate text-sm text-ink-faint hover:text-cobalt">
              <Link2 size={14} /> {r.source_url}
            </a>
          )}
          {r?.input_type === "image" && <p className="mb-4 text-sm text-ink-faint">The text we read from your screenshot</p>}
          {a.text ? (
            <AnnotatedText
              text={a.text}
              claims={a.claims}
              results={a.results}
              tactics={a.tactics}
              activeClaim={active}
              onSelectClaim={(id) => select(id, false)}
              showTactics={showTactics}
            />
          ) : (
            <p className="shimmer font-serif text-lg text-ink-faint">Reading the content…</p>
          )}
          {noSpans && <p className="mt-4 text-xs text-ink-faint">We reworded the facts to check them, so they're listed on the right instead of highlighted here.</p>}
        </article>
        <Legend />
      </div>

      {/* Right: verdict + notes */}
      <aside className="min-w-0 space-y-8">
        {r ? (
          <VerdictPanel result={r} />
        ) : (
          <div className="space-y-3" aria-hidden>
            <div className="shimmer-block h-7 w-32 rounded-full" />
            <div className="shimmer-block h-9 w-11/12 rounded" />
            <div className="shimmer-block h-4 w-full rounded" />
            <div className="shimmer-block h-4 w-4/5 rounded" />
          </div>
        )}
        <ClaimNotes claims={a.claims} results={a.results} activeClaim={active} onSelect={select} />
        {(a.style || r) && (
          <WritingSignals
            tactics={a.tactics}
            score={a.tacticsScore}
            style={a.style}
            showTactics={showTactics}
            onToggle={() => setShowTactics((x) => !x)}
          />
        )}
        {r && (
          <p className="border-t border-rule pt-4 text-xs leading-relaxed text-ink-faint">
            Checked{" "}
            {r.pipeline.timings_ms.total < 1000
              ? "in under a second"
              : `in ${(r.pipeline.timings_ms.total / 1000).toFixed(1)} seconds`}
            {r.pipeline.sources_used.length ? ` using ${r.pipeline.sources_used.map(sourceName).join(", ")}` : ""}
            {/claude/i.test(r.pipeline.llm_model || "") ? ", with help from Claude AI" : ""}. Computers can get this wrong, so open
            the sources before you rely on it.
          </p>
        )}
      </aside>
    </div>
  );
}

function Legend() {
  const items = [
    ["mark-refuted", "False"],
    ["mark-mixed", "Partly true"],
    ["mark-supported", "True"],
    ["mark-unverified", "Can't confirm"],
  ];
  return (
    <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs text-ink-soft">
      {items.map(([cls, label]) => (
        <span key={label} className="flex items-center gap-1.5">
          <span className={`claim-mark ${cls} px-2 py-0.5`}>&nbsp;</span>
          {label}
        </span>
      ))}
      <span className="flex items-center gap-1.5">
        <span className="tactic">wording</span> Warning-sign wording
      </span>
    </div>
  );
}
