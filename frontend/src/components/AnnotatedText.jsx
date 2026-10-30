/*
 * The left-hand panel of a result: your text, with claims highlighted by verdict
 * colour and persuasion tactics underlined with dotted lines.
 *
 * The tricky part is overlap: a tactic can sit inside a claim, or across two.
 * So we cut the text at every start/end position of every claim and tactic,
 * giving small "segments", then style each segment by whatever covers it.
 *
 *   text:     "BREAKING!!! Doctors say lemon water kills cancer."
 *   claim:                 [--------------------------------]
 *   tactics:  [------][--]
 *   segments: [BREAKING][!!!][ ][Doctors say lemon water kills cancer][.]
 */
import { useMemo } from "react";
import { CLAIM } from "../lib/verdicts.js";

/**
 * Renders the analysed text with claims highlighted by verdict and
 * persuasion tactics underlined. Overlaps are handled by cutting the text at
 * every span boundary and styling each segment by what covers it.
 */
export default function AnnotatedText({ text, claims, results, tactics, activeClaim, onSelectClaim, showTactics }) {
  const segments = useMemo(() => {
    const claimSpans = claims
      .filter((c) => c.span && c.span.end <= text.length)
      .map((c) => ({ id: c.id, start: c.span.start, end: c.span.end }));
    const tacticSpans = showTactics
      ? tactics.flatMap((t) => t.spans.filter((s) => s.end <= text.length).map((s) => ({ name: t.name, start: s.start, end: s.end })))
      : [];

    const cuts = new Set([0, text.length]);
    [...claimSpans, ...tacticSpans].forEach((s) => {
      cuts.add(s.start);
      cuts.add(s.end);
    });
    const points = [...cuts].sort((a, b) => a - b);

    const out = [];
    for (let i = 0; i < points.length - 1; i++) {
      const [a, b] = [points[i], points[i + 1]];
      if (a === b) continue;
      const claim = claimSpans.find((s) => s.start <= a && s.end >= b);
      const tactic = tacticSpans.filter((s) => s.start <= a && s.end >= b).map((s) => s.name);
      out.push({ key: a, text: text.slice(a, b), claim: claim?.id, tactics: [...new Set(tactic)] });
    }
    return out;
  }, [text, claims, tactics, showTactics]);

  return (
    <div className="annotated font-serif text-[1.075rem] leading-[1.8] text-ink whitespace-pre-wrap break-words">
      {segments.map((seg) => {
        if (seg.claim == null && !seg.tactics.length) return <span key={seg.key}>{seg.text}</span>;

        const tacticCls = seg.tactics.length ? "tactic" : "";
        const tacticTitle = seg.tactics.length ? `Persuasion tactic: ${seg.tactics.join(", ")}` : undefined;

        if (seg.claim == null) {
          return (
            <span key={seg.key} className={tacticCls} title={tacticTitle}>
              {seg.text}
            </span>
          );
        }
        const verdict = results[seg.claim]?.verdict || "PENDING";
        const v = CLAIM[verdict];
        const active = activeClaim === seg.claim;
        return (
          <mark
            key={seg.key}
            role="button"
            tabIndex={0}
            data-claim={seg.claim}
            title={tacticTitle || `${v.label}: click to see the evidence`}
            onClick={() => onSelectClaim(seg.claim)}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onSelectClaim(seg.claim))}
            className={`claim-mark ${v.mark} ${tacticCls} ${active ? "is-active" : ""}`}
          >
            {seg.text}
          </mark>
        );
      })}
    </div>
  );
}
