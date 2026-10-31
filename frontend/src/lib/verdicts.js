/*
 * Display settings for verdicts: the label shown to people and the colour classes.
 * Change a label or colour here and it changes everywhere on the site.
 * The colours themselves (refuted, mixed, supported, ...) are defined in tailwind.config.js.
 */

export const CLAIM = {
  REFUTED: { label: "False", tone: "refuted", text: "text-refuted", bg: "bg-refuted-wash", bar: "bg-refuted", mark: "mark-refuted" },
  MIXED: { label: "Partly true", tone: "mixed", text: "text-mixed", bg: "bg-mixed-wash", bar: "bg-mixed", mark: "mark-mixed" },
  SUPPORTED: { label: "True", tone: "supported", text: "text-supported", bg: "bg-supported-wash", bar: "bg-supported", mark: "mark-supported" },
  UNVERIFIABLE: { label: "Can't confirm", tone: "unverified", text: "text-unverified", bg: "bg-unverified-wash", bar: "bg-unverified", mark: "mark-unverified" },
  PENDING: { label: "Checking", tone: "pending", text: "text-ink-faint", bg: "bg-paper", bar: "bg-rule", mark: "mark-pending" },
};

export const OVERALL = {
  LIKELY_FALSE: { label: "Likely false", tone: CLAIM.REFUTED },
  NEEDS_CONTEXT: { label: "Partly true", tone: CLAIM.MIXED },
  LOOKS_RELIABLE: { label: "Looks true", tone: CLAIM.SUPPORTED },
  UNVERIFIED: { label: "Can't confirm", tone: CLAIM.UNVERIFIABLE },
  NO_CLAIMS: { label: "No facts to check", tone: CLAIM.UNVERIFIABLE },
};

export const SOURCE_KIND = {
  factcheck: "Fact-check",
  government: "Official",
  science: "Research",
  news: "News",
  encyclopedia: "Encyclopedia",
  web: "Web",
};

export const STANCE = {
  supports: { label: "Agrees", cls: "text-supported" },
  refutes: { label: "Disagrees", cls: "text-refuted" },
  mixed: { label: "Mixed", cls: "text-mixed" },
  neutral: { label: "", cls: "" },
};

// Friendly names for the evidence sources listed under a result.
const SOURCE_NAMES = { google_factcheck: "Google Fact Check", wikipedia: "Wikipedia", brave: "web search", tavily: "web search", claude_web_search: "web search" };
export const sourceName = (s) => SOURCE_NAMES[s] || s.replaceAll("_", " ");

export const pct = (x) => (x == null ? "–" : `${Math.round(x * 100)}%`);

export function confidenceWord(c) {
  if (c >= 0.75) return "Very sure";
  if (c >= 0.5) return "Fairly sure";
  if (c >= 0.25) return "Not very sure";
  return "Unsure";
}

export function timeAgo(iso) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}
