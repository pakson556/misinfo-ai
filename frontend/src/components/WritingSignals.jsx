/*
 * "How it's written": the persuasion tactics found (with example phrases and a
 * strength bar) and, if a style model is installed, its score. The checkbox turns
 * the dotted underlines in the text on or off.
 */
import { pct } from "../lib/verdicts.js";

export default function WritingSignals({ tactics, score, style, showTactics, onToggle }) {
  return (
    <section>
      <div className="flex items-center justify-between gap-4">
        <h3 className="text-sm font-semibold text-ink">How it's written</h3>
        {tactics.length > 0 && (
          <label className="flex cursor-pointer items-center gap-2 text-sm text-ink-soft">
            <input type="checkbox" checked={showTactics} onChange={onToggle} className="h-4 w-4 accent-cobalt" />
            Underline in text
          </label>
        )}
      </div>
      <p className="mt-1 text-sm leading-relaxed text-ink-soft">
        {tactics.length
          ? "These techniques push people to react or share. They don't make a claim false on their own."
          : "No common persuasion tactics found in the wording."}
      </p>

      {tactics.length > 0 && (
        <ul className="mt-3 space-y-3">
          {tactics.map((t) => (
            <li key={t.id} className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-0.5">
              <span className="text-[0.95rem] font-medium text-ink">{t.name}</span>
              <span className="self-center text-xs text-ink-faint">
                {t.spans.length} instance{t.spans.length !== 1 ? "s" : ""}
              </span>
              <span className="text-sm text-ink-soft">{t.description}</span>
              <span className="mt-1.5 h-1.5 w-16 self-start overflow-hidden rounded-full bg-rule" aria-label={`Strength ${pct(t.severity)}`}>
                <span className="block h-full rounded-full bg-mixed" style={{ width: `${t.severity * 100}%` }} />
              </span>
              {t.spans.length > 0 && (
                <span className="col-span-2 mt-1 flex flex-wrap gap-1.5">
                  {t.spans.slice(0, 4).map((s) => (
                    <q key={s.start} className="rounded bg-mixed-wash px-1.5 py-0.5 font-serif text-sm text-ink">
                      {s.text}
                    </q>
                  ))}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {style?.available && (
        <div className="mt-5 border-t border-rule pt-4 text-sm">
          <div className="flex justify-between">
            <span className="text-ink-soft">Resembles known misinformation</span>
            <span className="font-medium text-ink">{pct(style.probability)}</span>
          </div>
          <p className="mt-1 text-xs leading-relaxed text-ink-faint">{style.note}</p>
        </div>
      )}
      {score > 0 && <p className="sr-only">Overall persuasion intensity {pct(score)}</p>}
    </section>
  );
}
