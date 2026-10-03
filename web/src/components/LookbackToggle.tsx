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
      <div className="tabbar">
        {OPTIONS.map((y) => {
          const checked = value === y;
          return (
            <label
              key={y}
              className={`tab relative min-w-12 cursor-pointer has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-cta ${
                checked ? "tab-active" : ""
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
