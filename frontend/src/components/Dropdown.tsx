import { useEffect, useId, useRef, useState } from "react";
import { Chevron } from "./icons";
import styles from "./FilterBar.module.css";

export interface Option {
  value: string;
  label: string;
}

// A pill that opens a checkbox popover. Active (coral) whenever a value is
// selected. Closes on outside click or Escape.
export function Dropdown({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: Option[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const active = selected.length > 0;

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const toggle = (value: string) => {
    onChange(
      selected.includes(value)
        ? selected.filter((v) => v !== value)
        : [...selected, value],
    );
  };

  const buttonLabel =
    active && selected.length === 1
      ? (options.find((o) => o.value === selected[0])?.label ?? label)
      : active
        ? `${label} · ${selected.length}`
        : label;

  return (
    <div className={styles.dropdown} ref={ref}>
      <button
        className={`${styles.pill} ${active ? styles.pillActive : ""}`}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls={menuId}
      >
        {buttonLabel}
        <Chevron className={styles.chev} />
      </button>
      {open && (
        <div className={styles.menu} id={menuId} role="listbox">
          {options.map((opt) => {
            const checked = selected.includes(opt.value);
            return (
              <button
                key={opt.value}
                className={styles.menuItem}
                role="option"
                aria-selected={checked}
                onClick={() => toggle(opt.value)}
              >
                <span
                  className={`${styles.check} ${checked ? styles.checkOn : ""}`}
                >
                  {checked && (
                    <svg width="10" height="10" viewBox="0 0 12 12" aria-hidden>
                      <path
                        d="M2.5 6.2l2.2 2.2L9.5 3.5"
                        fill="none"
                        stroke="#fff"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                </span>
                {opt.label}
              </button>
            );
          })}
          {active && (
            <button className={styles.clearItem} onClick={() => onChange([])}>
              Clear
            </button>
          )}
        </div>
      )}
    </div>
  );
}
