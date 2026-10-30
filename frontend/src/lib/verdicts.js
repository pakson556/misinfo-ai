/*
 * Display settings for verdicts: the label shown to people and the colour classes.
 * Change a label or colour here and it changes everywhere on the site.
 * The colours themselves (refuted, mixed, supported, ...) are defined in tailwind.config.js.
 */

export const CLAIM = {
  REFUTED: { label: "False", tone: "refuted", text: "text-refuted", bg: "bg-refuted-wash", bar: "bg-refuted", mark: "mark-refuted" },
  MIXED: { label: "Needs context", tone: "mixed", text: "text-mixed", bg: "bg-mixed-wash", bar: "bg-mixed", mark: "mark-mixed" },
  SUPPORTED: { label: "True", tone: "supported", text: "text-supported", bg: "bg-supported-wash", bar: "bg-supported", mark: "mark-supported" },
  UNVERIFIABLE: { label: "Unverified", tone: "unverified", text: "text-unverified", bg: "bg-unverified-wash", bar: "bg-unverified", mark: "mark-unverified" },
  PENDING: { label: "Checking", tone: "pending", text: "text-ink-faint", bg: "bg-paper", bar: "bg-rule", mark: "mark-pending" },
};

export const OVERALL = {
  LIKELY_FALSE: { label: "Likely false", tone: CLAIM.REFUTED },
  NEEDS_CONTEXT: { label: "Needs context", tone: CLAIM.MIXED },
  LOOKS_RELIABLE: { label: "Looks reliable", tone: CLAIM.SUPPORTED },
  UNVERIFIED: { label: "Unverified", tone: CLAIM.UNVERIFIABLE },
  NO_CLAIMS: { label: "Nothing to check", tone: CLAIM.UNVERIFIABLE },
};

export const SOURCE_KIND = {
  factcheck: "Fact-check",
  government: "Official",
  science: "Research",
  news: "News",
  encyclopedia: "Reference",
  web: "Web",
};

export const STANCE = {
  supports: { label: "Supports", cls: "text-supported" },
  refutes: { label: "Contradicts", cls: "text-refuted" },
  mixed: { label: "Mixed", cls: "text-mixed" },
  neutral: { label: "", cls: "" },
};

export const pct = (x) => (x == null ? "–" : `${Math.round(x * 100)}%`);

export function confidenceWord(c) {
  if (c >= 0.75) return "Strong evidence";
  if (c >= 0.5) return "Moderate evidence";
  if (c >= 0.25) return "Limited evidence";
  return "Very little evidence";
}

export function timeAgo(iso) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}
