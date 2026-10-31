/*
 * "Warning signs in the wording": the persuasion tricks found (with example
 * phrases and a strength bar) and, if a style model is installed, a plain-words
 * reading of its score. The checkbox turns the dotted underlines on or off.
 */
import { pct } from "../lib/verdicts.js";

export default function WritingSignals({ tactics, score, style, showTactics, onToggle }) {
  return (
    <section>
      <div className="flex items-center justify-between gap-4">
        <h3 className="text-sm font-semibold text-ink">Warning signs in the wording</h3>
        {tactics.length > 0 && (
          <label className="flex cursor-pointer items-center gap-2 text-sm text-ink-soft">
            <input type="checkbox" checked={showTactics} onChange={onToggle} className="h-4 w-4 accent-cobalt" />
            Underline them in the text
          </label>
        )}
      </div>
      <p className="mt-1 text-sm leading-relaxed text-ink-soft">
        {tactics.length
          ? "Tricks often used to make people react or share without thinking. They don't make something false on their own."
          : "We didn't find any of the usual tricks in the wording."}
      </p>

      {tactics.length > 0 && (
        <ul className="mt-3 space-y-3">
          {tactics.map((t) => (
            <li key={t.id} className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-0.5">
              <span className="text-[0.95rem] font-medium text-ink">{t.name}</span>
              <span className="self-center text-xs text-ink-faint">
                {t.spans.length === 1 ? "found once" : `found ${t.spans.length} times`}
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

      {style?.available && <StyleHint style={style} />}
      {score > 0 && <p className="sr-only">Overall persuasion intensity {pct(score)}</p>}
    </section>
  );
}

// The style model's score in plain words. The exact number and how well the model
// tested sit under "More detail" for anyone who wants them.
function styleWords(p) {
  if (p < 0.35) return { label: "Like trustworthy writing", cls: "text-supported" };
  if (p < 0.6) return { label: "Hard to tell", cls: "text-ink" };
  return { label: "Like misinformation", cls: "text-mixed" };
}

function StyleHint({ style }) {
  const w = styleWords(style.probability ?? 0.5);
  return (
    <div className="mt-5 border-t border-rule pt-4 text-sm">
      <div className="flex justify-between gap-4">
        <span className="text-ink-soft">Writing style</span>
        <span className={`font-medium ${w.cls}`}>{w.label}</span>
      </div>
      <p className="mt-1 text-sm leading-relaxed text-ink-soft">
        A small hint from our AI about how this is written. It doesn't check facts, so the verdict at the top matters more.
      </p>
      <details className="mt-2 text-xs leading-relaxed text-ink-faint">
        <summary className="cursor-pointer text-ink-soft hover:text-ink">More detail</summary>
        <p className="mt-1">
          It looks {pct(style.probability)} like the false posts it learned from. {style.note}
        </p>
      </details>
    </div>
  );
}
