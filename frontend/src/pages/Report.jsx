/*
 * /a/<id>: shows one saved check, loaded from the backend's history.
 * This is what a "Copy link" link opens.
 */
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import ResultView from "../components/ResultView.jsx";
import { api } from "../lib/api.js";
import { useAnalysis } from "../lib/useAnalysis.js";
import { timeAgo } from "../lib/verdicts.js";

export default function Report() {
  const { id } = useParams();
  const a = useAnalysis();
  const { load } = a;
  const [error, setError] = useState("");

  useEffect(() => {
    api.analysis(id).then(load).catch((e) => setError(e.message));
  }, [id, load]);

  if (error) {
    return (
      <div className="mx-auto max-w-xl pt-16">
        <h1 className="font-serif text-2xl text-ink">This check isn't available</h1>
        <p className="mt-2 text-ink-soft">It may have been deleted. {error}</p>
        <Link to="/" className="mt-4 inline-block font-medium text-cobalt">Start a new check</Link>
      </div>
    );
  }
  if (!a.result) return <p className="pt-16 text-center text-ink-faint">Loading…</p>;

  return (
    <div className="pt-6">
      <p className="mb-6 text-sm text-ink-faint">Checked {timeAgo(a.result.created_at)}</p>
      <ResultView a={a} />
    </div>
  );
}
