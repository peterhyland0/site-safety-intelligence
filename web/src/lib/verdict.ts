import type { Severity, SubCard, Verdict } from "../api/types";

export interface VerdictMeta {
  /** Fallback label if the server's verdict_label is missing */
  label: string;
  /** One-line plain-English meaning, used in tooltips, legends and the methodology page */
  meaning: string;
  chip: string;
  /** Left accent on the card */
  accent: string;
  icon: "high" | "review" | "unknown" | "recent" | "clear";
  rank: number;
}

export const VERDICTS: Record<Verdict, VerdictMeta> = {
  high: {
    label: "High concern",
    meaning:
      "OSHA record shows a serious event in the last 10 years (a cited fatality, a willful violation or a failure to abate), repeat violations across inspections, or a serious-citation rate in the trade's top 10%.",
    chip: "bg-high-bg text-high-fg border-high-line",
    accent: "border-l-high-fg",
    icon: "high",
    rank: 0,
  },
  review: {
    label: "Review",
    meaning:
      "OSHA record shows something worth a conversation, such as a repeat violation, a recurring hazard, an open case with serious citations or a serious rate above most of the trade.",
    chip: "bg-review-bg text-review-fg border-review-line",
    accent: "border-l-review-fg",
    icon: "review",
    rank: 1,
  },
  no_record: {
    label: "No OSHA record",
    meaning: "No inspections found under this name. That means unknown, not clean: OSHA inspects only a small share of firms.",
    chip: "bg-unknown-bg text-unknown-fg border-unknown-line border-dashed",
    accent: "border-l-unknown-line",
    icon: "unknown",
    rank: 2,
  },
  no_recent: {
    label: "No recent record",
    meaning: "Inspections exist, but none inside the lookback window. Older history is still listed.",
    chip: "bg-recent-bg text-recent-fg border-recent-line",
    accent: "border-l-recent-fg",
    icon: "recent",
    rank: 3,
  },
  no_flags: {
    label: "No flags",
    meaning: "Inspected within the window and nothing in the OSHA record met a concern rule.",
    chip: "bg-clear-bg text-clear-fg border-clear-line",
    accent: "border-l-clear-fg",
    icon: "clear",
    rank: 4,
  },
};

export const VERDICT_ORDER: Verdict[] = ["high", "review", "no_record", "no_recent", "no_flags"];

export const SEVERITY_META: Record<Severity, { label: string; dot: string }> = {
  high: { label: "High", dot: "bg-high-fg" },
  review: { label: "Review", dot: "bg-review-fg" },
  info: { label: "Info", dot: "bg-muted" },
};

/** Plain-English comparison of the sub's serious+ rate with its trade benchmark. */
export function rateComparison(card: SubCard): string | null {
  const { serious_plus_rate: r, trade_p50: p50, trade_p75: p75 } = card;
  if (r == null || p50 == null) return null;
  if (p75 != null && r >= p75) return "above most of the trade (75th percentile)";
  if (r > p50) return "above the trade median";
  return "at or below the trade median";
}
