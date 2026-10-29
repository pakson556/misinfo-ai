import { Suspense, lazy, useEffect, useState } from "react";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import { api } from "./lib/api.js";
import Check from "./pages/Check.jsx";
import History from "./pages/History.jsx";
import Report from "./pages/Report.jsx";

const Insights = lazy(() => import("./pages/Insights.jsx"));

function Header() {
  const [health, setHealth] = useState(null);
  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ status: "down" }));
  }, []);

  const link = ({ isActive }) =>
    `rounded-md px-2.5 py-1.5 text-sm sm:px-3 font-medium transition-colors ${isActive ? "bg-ink text-paper" : "text-ink-soft hover:text-ink"}`;

  return (
    <header className="border-b border-rule bg-paper/90 backdrop-blur supports-[backdrop-filter]:bg-paper/75 sticky top-0 z-20">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <NavLink to="/" className="flex items-center gap-2.5" aria-label="MisInfo AI home">
          <img src="/favicon.svg" alt="" className="h-7 w-7" />
          <span className="whitespace-nowrap font-serif text-lg font-[650] tracking-tight text-ink">MisInfo AI</span>
        </NavLink>
        <nav className="flex items-center gap-0.5 sm:gap-1">
          <NavLink to="/" end className={link}>Check</NavLink>
          <NavLink to="/history" className={link}>History</NavLink>
          <NavLink to="/insights" className={link}>Insights</NavLink>
        </nav>
      </div>
      {health && health.status !== "ok" && (
        <p role="status" className="bg-refuted-wash px-4 py-2 text-center text-sm text-refuted">
          The analysis server isn't responding. Checks won't work until it's running.
        </p>
      )}
      {health?.status === "ok" && !health.llm_ready && (
        <p role="status" className="bg-mixed-wash px-4 py-2 text-center text-sm text-mixed">
          Running in basic mode: no AI model is configured, so only published fact-checks can be matched.
        </p>
      )}
    </header>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-paper">
        <Header />
        <main className="mx-auto max-w-7xl px-4 pb-20 sm:px-6">
          <Routes>
            <Route path="/" element={<Check />} />
            <Route path="/a/:id" element={<Report />} />
            <Route path="/history" element={<History />} />
            <Route path="/insights" element={<Suspense fallback={<p className="pt-10 text-ink-faint">Loading…</p>}><Insights /></Suspense>} />
            <Route path="*" element={<p className="pt-16 text-center text-ink-soft">That page doesn't exist.</p>} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
