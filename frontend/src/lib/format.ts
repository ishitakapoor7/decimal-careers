import type { Job } from "../api/types";

// "$165K–$215K" from raw salary integers.
export function salaryRange(min: number, max: number): string {
  const k = (n: number) => `$${Math.round(n / 1000)}K`;
  if (!min && !max) return "Salary not listed";
  if (min && max) return `${k(min)}–${k(max)}`;
  return k(min || max);
}

// "2026-06-09" → "Jun 9". Dates from the API are ISO date strings.
export function shortDate(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso.length <= 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// Title-case an enum value like "full_time" → "Full-time", "remote" → "Remote".
export function humanize(value: string): string {
  if (!value) return "";
  return value
    .split("_")
    .map((w, i) => (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w))
    .join("-");
}

// "Northwind Labs · London, England". Work mode is shown as a tag, not here,
// so we don't repeat it in the meta line — just company and location.
export function jobMeta(job: Job): string {
  const place = [job.city, job.state_region].filter(Boolean).join(", ");
  return [job.company, place].filter(Boolean).join(" · ");
}

// Work-mode tag label. Remote carries the country it's based in (the office
// city is shown separately in the meta line), e.g. "Remote (US)" / "Remote (UK)".
export function workModeLabel(job: Job): string {
  if (job.work_mode === "remote") return `Remote (${countryCode(job.country)})`;
  return humanize(job.work_mode);
}

function countryCode(country: string): string {
  const map: Record<string, string> = {
    USA: "US",
    UK: "UK",
    India: "IN",
    Germany: "DE",
  };
  return map[country] ?? country.slice(0, 2).toUpperCase();
}

// Tag palette: work mode and team each get a tint, matching the design.
export type Tone = "teal" | "gold" | "neutral" | "pink" | "coral";

export function workModeTone(mode: string): Tone {
  if (mode === "remote") return "teal";
  if (mode === "hybrid") return "gold";
  return "neutral"; // onsite
}

export function teamTone(team: string): Tone {
  if (team === "design") return "pink";
  if (team === "engineering") return "coral";
  return "neutral";
}

export function initial(company: string): string {
  return (company.trim()[0] ?? "?").toUpperCase();
}
