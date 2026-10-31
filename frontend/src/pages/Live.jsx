/*
 * The Live page (/live): public Bluesky posts that use common misinformation
 * tricks, as they are written. Asks the backend (GET /api/monitor) every 5 seconds.
 *
 * No names or accounts are shown. Being listed is not a verdict: each post has a
 * "Check it" button that sends its text to the Check page for a proper fact-check.
 */
import { Radio } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";
import { timeAgo } from "../lib/verdicts.js";

const fmt = new Intl.NumberFormat();

export default function Live() {
  const [m, setM] = useState(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    let alive = true;
    const load = () =>
      api
        .monitor()
        .then((d) => alive && (setM(d), setError("")))
        .catch((e) => alive && setError(e.message));
    load();
    const timer = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  const share = m && m.seen ? m.flagged / m.seen : 0;
  const maxTactic = Math.max(1, ...(m?.top_tactics || []).map((t) => t.count));

  return (
    <div className="mx-auto max-w-5xl pt-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-serif text-3xl font-[650] text-ink">Live monitor</h1>
        <Status m={m} />
      </div>
      <p className="mt-3 max-w-[62ch] leading-relaxed text-ink-soft">
        Public posts on Bluesky, read as they are written. Posts that use common misinformation tricks appear below,
        without names. Being listed doesn't mean a post is false. Press <span className="font-medium text-ink">Check it</span> to look up the facts.
      </p>

      {error && <p className="mt-6 text-sm text-refuted">{error}</p>}

      {m && !m.enabled && (
        <div className="mt-8 rounded-xl border border-rule bg-sheet p-6 text-sm leading-relaxed text-ink-soft">
          <p className="font-medium text-ink">The live monitor is switched off.</p>
          <p className="mt-1">
            To switch it on, add the line <code className="rounded bg-paper px-1.5 py-0.5">MONITOR_ENABLED=true</code> to{" "}
            <code className="rounded bg-paper px-1.5 py-0.5">backend/.env</code> and restart the app.
          </p>
        </div>
      )}

      {m?.enabled && (
        <>
          <section className="mt-8 grid gap-4 sm:grid-cols-3">
            <Tile label="Posts read" value={fmt.format(m.seen)} />
            <Tile label="Posts with warning signs" value={fmt.format(m.flagged)} />
            <Tile label="Share with warning signs" value={m.seen ? `${(share * 100).toFixed(1)}%` : "–"} />
          </section>

          <div className="mt-8 grid gap-8 lg:grid-cols-[minmax(0,1fr)_18rem]">
            <section className="min-w-0">
              <h2 className="text-sm font-semibold text-ink">Recently flagged posts</h2>
              {m.recent.length === 0 ? (
                <p className="mt-3 text-sm text-ink-faint">
                  {m.connected ? "Nothing flagged yet. Posts appear here as they are written." : "Connecting to Bluesky…"}
                </p>
              ) : (
                <ul className="mt-3 space-y-3">
                  {m.recent.map((p) => (
                    <li key={p.time + p.text} className="rounded-xl border border-rule bg-sheet p-4">
                      <p className="font-serif text-[1.02rem] leading-relaxed text-ink">{p.text}</p>
                      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                        <span className="flex flex-wrap gap-1.5">
                          {p.tactics.map((t) => (
                            <span key={t} className="rounded-full bg-mixed-wash px-2.5 py-0.5 text-xs text-mixed">
                              {t}
                            </span>
                          ))}
                        </span>
                        <span className="flex items-center gap-3 text-xs text-ink-faint">
                          {timeAgo(p.time)}
                          <button
                            type="button"
                            onClick={() => navigate("/", { state: { text: p.text } })}
                            className="rounded-lg bg-ink px-3 py-1.5 text-xs font-semibold text-paper hover:bg-cobalt"
                          >
                            Check it
                          </button>
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <aside>
              <h2 className="text-sm font-semibold text-ink">Most common warning signs</h2>
              {m.top_tactics.length === 0 ? (
                <p className="mt-3 text-sm text-ink-faint">None yet.</p>
              ) : (
                <ul className="mt-3 space-y-3">
                  {m.top_tactics.map((t) => (
                    <li key={t.id}>
                      <div className="flex justify-between text-sm">
                        <span className="text-ink">{t.name}</span>
                        <span className="tabular-nums text-ink-faint">{fmt.format(t.count)}</span>
                      </div>
                      <div className="mt-1 h-1.5 rounded-full bg-rule">
                        <div className="h-full rounded-full bg-mixed" style={{ width: `${(t.count / maxTactic) * 100}%` }} />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-6 text-xs leading-relaxed text-ink-faint">
                Counting started {m.started ? timeAgo(m.started) : "at start-up"}. Nothing is saved: the list resets when the app restarts.
              </p>
            </aside>
          </div>
        </>
      )}
    </div>
  );
}

function Tile({ label, value }) {
  return (
    <div className="rounded-xl border border-rule bg-sheet p-5">
      <p className="text-sm text-ink-soft">{label}</p>
      <p className="mt-1 font-serif text-3xl tabular-nums text-ink">{value}</p>
    </div>
  );
}

function Status({ m }) {
  if (!m?.enabled) return null;
  return (
    <span className={`inline-flex items-center gap-2 text-sm ${m.connected ? "text-supported" : "text-ink-faint"}`}>
      <Radio size={16} className={m.connected ? "animate-pulse" : ""} />
      {m.connected ? "Live" : "Reconnecting…"}
    </span>
  );
}
