import type { Tone } from "../lib/format";
import styles from "./Tag.module.css";

// Small rounded pill used for work mode, team, and detail-header chips.
export function Tag({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: Tone;
}) {
  return <span className={`${styles.tag} ${styles[tone]}`}>{children}</span>;
}
