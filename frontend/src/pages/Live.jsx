/*
 * The Live page (/live): public Bluesky posts that use common misinformation
 * tricks, as they are written. Asks the backend (GET /api/monitor) every 5 seconds.
 *
 * No names or accounts are shown. Being listed is not a verdict: each post has a
 * "Check it" button that sends its text to the Check page for a proper fact-check.
 */
import { ExternalLink, Radio } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api.js";
import { CLAIM, timeAgo } from "../lib/verdicts.js";

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
        Public posts on Bluesky, read as they are written, plus news from around the world (further down). Posts that use common misinformation tricks appear below,
        without names, and are looked up in published fact-checks. Being listed doesn't mean a post is false. Press{" "}
        <span className="font-medium text-ink">Check it</span> for a full check.
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
          <section className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Tile label="Posts read" value={fmt.format(m.seen)} />
            <Tile label="Posts with warning signs" value={fmt.format(m.flagged)} />
            <Tile label="Share with warning signs" value={m.seen ? `${(share * 100).toFixed(1)}%` : "–"} />
            <Tile
              label="Matched a published fact-check"
              value={m.factcheck_enabled ? fmt.format(m.matched) : "Off"}
              note={m.factcheck_enabled ? `${fmt.format(m.looked_up)} looked up so far` : "Needs the Google Fact Check key"}
            />
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
                      {p.factcheck && <FactCheck fc={p.factcheck} />}
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
              {m.matched_claims?.length > 0 && (
                <div className="mb-8">
                  <h2 className="text-sm font-semibold text-ink">Claims fact-checkers have rated</h2>
                  <p className="mt-1 text-xs leading-relaxed text-ink-faint">Seen in posts since start-up, most often first.</p>
                  <ul className="mt-3 space-y-3">
                    {m.matched_claims.map((c) => (
                      <li key={c.url} className="text-sm">
                        <a href={c.url} target="_blank" rel="noopener noreferrer" className="group block">
                          <span className="text-ink group-hover:text-cobalt">{c.claim}</span>
                          <span className="mt-0.5 block text-xs text-ink-faint">
                            <span className={`font-medium ${(CLAIM[c.verdict] || CLAIM.UNVERIFIABLE).text}`}>“{c.rating}”</span> ·{" "}
                            {c.publisher} · seen {c.count === 1 ? "once" : `${c.count} times`}
                          </span>
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
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

          <WorldNews m={m} />
        </>
      )}
    </div>
  );
}

// News articles from around the world about false claims, hoaxes and fact-checks (from GDELT).
function WorldNews({ m }) {
  const maxCountry = Math.max(1, ...(m.news_by_country || []).map((c) => c.count));
  return (
    <section className="mt-14 border-t border-rule pt-8">
      <h2 className="font-serif text-2xl font-[650] text-ink">Misinformation in the news worldwide</h2>
      <p className="mt-2 max-w-[62ch] text-sm leading-relaxed text-ink-soft">
        News stories from the last 24 hours, from any country, about false claims, hoaxes and fact-checks. Collected by GDELT,
        a free project that reads news in over 100 languages. Updated every 15 minutes.
      </p>
      {m.news_error && <p className="mt-4 text-sm text-mixed">{m.news_error}</p>}
      {!m.news?.length ? (
        !m.news_error && <p className="mt-4 text-sm text-ink-faint">Loading world news…</p>
      ) : (
        <div className="mt-6 grid gap-8 lg:grid-cols-[minmax(0,1fr)_18rem]">
          <ul className="min-w-0 divide-y divide-rule rounded-xl border border-rule bg-sheet">
            {m.news.map((a) => (
              <li key={a.url}>
                <a href={a.url} target="_blank" rel="noopener noreferrer" className="group block px-4 py-3">
                  <span className="flex items-start gap-1.5 text-[0.95rem] leading-snug text-ink group-hover:text-cobalt">
                    {a.title}
                    <ExternalLink size={13} className="mt-1 shrink-0 opacity-50" aria-hidden />
                  </span>
                  <span className="mt-1 block text-xs text-ink-faint">
                    {[a.site, a.country, a.language !== "English" ? a.language : "", a.time ? timeAgo(a.time) : ""]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                </a>
              </li>
            ))}
          </ul>
          <aside>
            <h3 className="text-sm font-semibold text-ink">Where these stories come from</h3>
            <ul className="mt-3 space-y-3">
              {m.news_by_country.map((c) => (
                <li key={c.country}>
                  <div className="flex justify-between text-sm">
                    <span className="text-ink">{c.country}</span>
                    <span className="tabular-nums text-ink-faint">{c.count}</span>
                  </div>
                  <div className="mt-1 h-1.5 rounded-full bg-rule">
                    <div className="h-full rounded-full bg-cobalt" style={{ width: `${(c.count / maxCountry) * 100}%` }} />
                  </div>
                </li>
              ))}
            </ul>
            {m.news_updated && <p className="mt-6 text-xs text-ink-faint">Last updated {timeAgo(m.news_updated)}.</p>}
          </aside>
        </div>
      )}
    </section>
  );
}

function Tile({ label, value, note }) {
  return (
    <div className="rounded-xl border border-rule bg-sheet p-5">
      <p className="text-sm text-ink-soft">{label}</p>
      <p className="mt-1 font-serif text-3xl tabular-nums text-ink">{value}</p>
      {note && <p className="mt-1 text-xs text-ink-faint">{note}</p>}
    </div>
  );
}

// A published fact-check about a claim very close to this post.
function FactCheck({ fc }) {
  const tone = CLAIM[fc.verdict] || CLAIM.UNVERIFIABLE;
  return (
    <a
      href={fc.url}
      target="_blank"
      rel="noopener noreferrer"
      className={`mt-3 flex items-start gap-2 rounded-lg px-3 py-2 text-sm ${tone.bg} hover:underline`}
    >
      <span>
        A fact-checker reviewed a very similar claim. <span className="font-medium">{fc.publisher}</span> rated it{" "}
        <span className={`font-semibold ${tone.text}`}>“{fc.rating}”</span>.
      </span>
      <ExternalLink size={14} className="mt-1 shrink-0 opacity-60" aria-hidden />
    </a>
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
