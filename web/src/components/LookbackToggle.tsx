import { useId } from "react";
import type { LookbackYears } from "../api/types";

const OPTIONS: LookbackYears[] = [3, 5, 10];

/** Segmented radio group for the lookback window (3 / 5 / 10 years). */
export function LookbackToggle({
  value,
  onChange,
  disabled = false,
  label = "Lookback",
}: {
  value: number;
  onChange: (v: LookbackYears) => void;
  disabled?: boolean;
  label?: string;
}) {
  const name = useId();
  return (
    <fieldset className="flex items-center gap-2" disabled={disabled}>
      <legend className="sr-only">{label} window in years</legend>
      <span aria-hidden="true" className="text-sm text-muted">
        {label}
      </span>
      <div className="inline-flex rounded-lg border border-line-strong bg-surface p-0.5">
        {OPTIONS.map((y) => {
          const checked = value === y;
          return (
            <label
              key={y}
              className={`relative inline-flex min-h-9 min-w-12 cursor-pointer items-center justify-center rounded-md px-2.5 text-sm font-medium has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent ${
                checked ? "bg-accent text-accent-ink" : "text-ink-2 hover:bg-surface-2"
              }`}
            >
              <input
                type="radio"
                name={name}
                value={y}
                checked={checked}
                onChange={() => onChange(y)}
                className="sr-only"
              />
              {y} yr
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
