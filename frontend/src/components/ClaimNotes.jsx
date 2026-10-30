/*
 * The list of checked claims on the right: one "note" per claim, with its
 * verdict, the AI's reasoning, and its sources (fact-checks first).
 * Hovering or clicking a note highlights the matching words in the text, and vice versa.
 */
import { ExternalLink } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { CLAIM, SOURCE_KIND, STANCE, pct } from "../lib/verdicts.js";

function Source({ e }) {
  const stance = STANCE[e.stance] || STANCE.neutral;
  return (
    <li className="py-2.5">
      <a href={e.url} target="_blank" rel="noopener noreferrer" className="group block focus-visible:outline-none">
        <span className="flex items-center gap-2 text-xs text-ink-faint">
          <span className="font-medium text-ink-soft">{e.publisher || e.domain}</span>
          <span className="rounded bg-paper px-1.5 py-px">{SOURCE_KIND[e.kind] || "Web"}</span>
          {stance.label && <span className={`font-medium ${stance.cls}`}>{stance.label}</span>}
          {e.published && <span>{String(e.published).slice(0, 10)}</span>}
        </span>
        <span className="mt-0.5 flex items-start gap-1.5 text-[0.93rem] leading-snug text-ink group-hover:text-cobalt group-focus-visible:underline">
          {e.title || e.domain}
          <ExternalLink size={13} className="mt-1 shrink-0 opacity-50" aria-hidden />
        </span>
        {e.rating && (
          <span className="mt-1 block text-sm text-ink-soft">
            Rated <span className="font-medium text-ink">“{e.rating}”</span>
          </span>
        )}
      </a>
    </li>
  );
}

function Note({ claim, result, active, onSelect, index }) {
  const v = CLAIM[result?.verdict || "PENDING"];
  const [all, setAll] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (active) ref.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [active]);

  const evidence = result?.evidence || [];
  const shown = all ? evidence : evidence.slice(0, 3);

  return (
    <li
      ref={ref}
      className={`relative border-t border-rule py-5 pl-5 transition-colors first:border-t-0 ${active ? "bg-sheet" : ""}`}
      onMouseEnter={() => onSelect(claim.id, false)}
    >
      <span className={`absolute left-0 top-5 bottom-5 w-[3px] rounded-full ${v.bar}`} aria-hidden />
      <div className="flex items-center justify-between gap-3">
        <span className={`text-sm font-semibold ${v.text}`}>
          {result ? v.label : <span className="shimmer">Checking claim {index + 1}…</span>}
        </span>
        {result && result.verdict !== "UNVERIFIABLE" && (
          <span className="text-xs text-ink-faint">{pct(result.confidence)} confidence</span>
        )}
      </div>
      <button
        type="button"
        onClick={() => onSelect(claim.id, true)}
        className="mt-1.5 text-left font-serif text-[1.05rem] leading-snug text-ink focus-visible:underline focus-visible:outline-none"
      >
        {claim.text}
      </button>
      {result?.reasoning && <p className="mt-2 text-[0.94rem] leading-relaxed text-ink-soft">{result.reasoning}</p>}

      {evidence.length > 0 && (
        <>
          <ul className="mt-2 divide-y divide-rule/70">
            {shown.map((e) => (
              <Source key={e.url} e={e} />
            ))}
          </ul>
          {evidence.length > 3 && (
            <button type="button" onClick={() => setAll((x) => !x)} className="mt-1 text-sm font-medium text-cobalt hover:text-cobalt-deep">
              {all ? "Show fewer sources" : `Show all ${evidence.length} sources`}
            </button>
          )}
        </>
      )}
      {result && evidence.length === 0 && result.verdict === "UNVERIFIABLE" && (
        <p className="mt-2 text-sm text-ink-faint">No reliable sources found for this claim.</p>
      )}
    </li>
  );
}

export default function ClaimNotes({ claims, results, activeClaim, onSelect }) {
  if (!claims.length) return null;
  return (
    <section>
      <h3 className="text-sm font-semibold text-ink">
        {claims.length} claim{claims.length > 1 ? "s" : ""} checked
      </h3>
      <ol className="mt-2">
        {claims.map((c, i) => (
          <Note key={c.id} index={i} claim={c} result={results[c.id]} active={activeClaim === c.id} onSelect={onSelect} />
        ))}
      </ol>
    </section>
  );
}
