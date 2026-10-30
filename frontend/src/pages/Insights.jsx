/*
 * /insights: totals across all checks: checks per day (bar chart, using the
 * Recharts library), verdict breakdowns, and the most common persuasion tactics.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../lib/api.js";
import { CLAIM, OVERALL } from "../lib/verdicts.js";

const HEX = { refuted: "#B4232C", mixed: "#A86A12", supported: "#1D7352", unverified: "#667085" };

function Breakdown({ title, data, meta }) {
  const total = Object.values(data).reduce((a, b) => a + b, 0) || 1;
  const rows = Object.entries(data).sort((a, b) => b[1] - a[1]);
  return (
    <section>
      <h2 className="text-sm font-semibold text-ink">{title}</h2>
      <ul className="mt-3 space-y-2.5">
        {rows.map(([k, n]) => {
          const m = meta[k];
          const tone = m?.tone?.tone || m?.tone || "unverified";
          return (
            <li key={k} className="grid grid-cols-[9rem_1fr_3rem] items-center gap-3 text-sm">
              <span className="text-ink-soft">{m?.label || k}</span>
              <span className="h-2 overflow-hidden rounded-full bg-rule">
                <span className="block h-full rounded-full" style={{ width: `${(n / total) * 100}%`, background: HEX[tone] }} />
              </span>
              <span className="text-right tabular-nums text-ink">{n}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export default function Insights() {
  const [s, setS] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.stats(30).then(setS).catch((e) => setError(e.message));
  }, []);

  if (error) return <p role="alert" className="mx-auto max-w-4xl pt-10 text-refuted">{error}</p>;
  if (!s) return <p className="mx-auto max-w-4xl pt-10 text-ink-faint">Loading…</p>;
  if (!s.total)
    return (
      <div className="mx-auto max-w-4xl pt-8">
        <h1 className="font-serif text-3xl font-[650] text-ink">Insights</h1>
        <p className="mt-4 text-ink-soft">
          Patterns across your checks will show up here. <Link to="/" className="font-medium text-cobalt">Run your first check</Link>.
        </p>
      </div>
    );

  const claimMeta = Object.fromEntries(Object.entries(CLAIM).map(([k, v]) => [k, { label: v.label, tone: v.tone }]));
  const falseShare = Math.round(((s.by_overall.LIKELY_FALSE || 0) / s.total) * 100);

  return (
    <div className="mx-auto max-w-5xl pt-8">
      <h1 className="font-serif text-3xl font-[650] text-ink">Insights</h1>
      <p className="mt-2 max-w-[60ch] text-ink-soft">
        Across {s.total} check{s.total !== 1 ? "s" : ""}, {falseShare}% contained at least one claim that reliable sources contradict.
        {s.avg_latency_ms ? ` A check takes about ${(s.avg_latency_ms / 1000).toFixed(0)} seconds on average.` : ""}
      </p>

      <section className="mt-8 rounded-xl border border-rule bg-sheet p-5">
        <h2 className="text-sm font-semibold text-ink">Checks per day, last 30 days</h2>
        <div className="mt-4 h-56">
          <ResponsiveContainer>
            <BarChart data={s.daily} margin={{ left: -20, right: 8 }}>
              <CartesianGrid vertical={false} stroke="#DDE1E8" />
              <XAxis dataKey="date" tickFormatter={(d) => d.slice(5)} tick={{ fontSize: 12, fill: "#8A93A6" }} axisLine={false} tickLine={false} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12, fill: "#8A93A6" }} axisLine={false} tickLine={false} />
              <Tooltip cursor={{ fill: "#EEF1F5" }} contentStyle={{ borderRadius: 8, border: "1px solid #DDE1E8", fontSize: 13 }} />
              <Bar dataKey="count" name="Checks" isAnimationActive={false} maxBarSize={28} fill="#18202E" radius={[3, 3, 0, 0]} />
              <Bar dataKey="likely_false" name="Likely false" isAnimationActive={false} maxBarSize={28} fill="#B4232C" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <div className="mt-10 grid gap-10 md:grid-cols-2">
        <Breakdown title="Overall verdicts" data={s.by_overall} meta={OVERALL} />
        <Breakdown title="Individual claims" data={s.by_claim_verdict} meta={claimMeta} />
      </div>

      {s.top_tactics.length > 0 && (
        <section className="mt-10">
          <h2 className="text-sm font-semibold text-ink">Most common persuasion tactics</h2>
          <ul className="mt-3 divide-y divide-rule border-y border-rule">
            {s.top_tactics.map((t) => (
              <li key={t.id} className="flex justify-between py-2.5 text-sm">
                <span className="text-ink">{t.name}</span>
                <span className="tabular-nums text-ink-soft">found in {t.count} check{t.count !== 1 ? "s" : ""}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
