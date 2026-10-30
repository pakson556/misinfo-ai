/*
 * /history: every past check, newest first, with its verdict colour and preview.
 * Click one to reopen it; the bin icon deletes it.
 */
import { FileText, ImageIcon, Link2, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api.js";
import { OVERALL, pct, timeAgo } from "../lib/verdicts.js";

const ICON = { text: FileText, url: Link2, image: ImageIcon };

export default function History() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.history(100).then(setItems).catch((e) => setError(e.message));
  }, []);

  const remove = async (id) => {
    if (!confirm("Delete this check? This can't be undone.")) return;
    try {
      await api.remove(id);
      setItems((xs) => xs.filter((x) => x.id !== id));
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="mx-auto max-w-4xl pt-8">
      <h1 className="font-serif text-3xl font-[650] text-ink">Past checks</h1>
      {error && <p role="alert" className="mt-4 text-sm text-refuted">{error}</p>}
      {items && items.length === 0 && (
        <p className="mt-6 text-ink-soft">
          No checks yet. <Link to="/" className="font-medium text-cobalt">Check something</Link> and it will appear here.
        </p>
      )}
      {items === null && !error && <p className="mt-6 text-ink-faint">Loading…</p>}
      <ul className="mt-6 divide-y divide-rule border-y border-rule">
        {items?.map((it) => {
          const o = OVERALL[it.overall];
          const Icon = ICON[it.input_type] || FileText;
          return (
            <li key={it.id} className="group flex items-start gap-4 py-4">
              <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${o.tone.bar}`} aria-hidden />
              <Link to={`/a/${it.id}`} className="min-w-0 flex-1 focus-visible:outline-none">
                <span className="flex flex-wrap items-center gap-x-3 text-sm">
                  <span className={`font-semibold ${o.tone.text}`}>{o.label}</span>
                  <span className="text-ink-faint">{it.n_claims} claim{it.n_claims !== 1 ? "s" : ""}</span>
                  <span className="text-ink-faint">risk {pct(it.risk)}</span>
                  <span className="text-ink-faint">{timeAgo(it.created_at)}</span>
                </span>
                <span className="mt-1 flex gap-2 font-serif text-[1.02rem] leading-snug text-ink group-hover:text-cobalt group-focus-visible:underline">
                  <Icon size={15} className="mt-1 shrink-0 text-ink-faint" aria-hidden />
                  <span className="line-clamp-2">{it.input_preview || "(text not stored)"}</span>
                </span>
              </Link>
              <button
                type="button"
                onClick={() => remove(it.id)}
                aria-label="Delete this check"
                className="rounded p-1.5 text-ink-faint opacity-0 hover:bg-refuted-wash hover:text-refuted focus:opacity-100 group-hover:opacity-100"
              >
                <Trash2 size={16} />
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
