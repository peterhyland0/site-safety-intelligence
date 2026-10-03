import type { Verdict } from "../api/types";
import { VERDICTS } from "../lib/verdict";
import { IconCheckCircle, IconClock, IconOctagonAlert, IconTriangleAlert, IconUnknown } from "./Icons";

export function VerdictIcon({ verdict, size = 16 }: { verdict: Verdict; size?: number }) {
  switch (VERDICTS[verdict].icon) {
    case "high":
      return <IconOctagonAlert size={size} />;
    case "review":
      return <IconTriangleAlert size={size} />;
    case "unknown":
      return <IconUnknown size={size} />;
    case "recent":
      return <IconClock size={size} />;
    case "clear":
      return <IconCheckCircle size={size} />;
  }
}

export function VerdictChip({
  verdict,
  label,
  size = "md",
}: {
  verdict: Verdict;
  label?: string | null;
  size?: "md" | "lg";
}) {
  const meta = VERDICTS[verdict];
  const text = label || meta.label;
  const sizing = size === "lg" ? "px-3 py-1.5 text-base gap-2" : "px-2.5 py-1 text-sm gap-1.5";
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full border font-semibold whitespace-nowrap ${sizing} ${meta.chip}`}
      title={meta.meaning}
    >
      <VerdictIcon verdict={verdict} size={size === "lg" ? 18 : 16} />
      <span>{text}</span>
    </span>
  );
}
