import { Dropdown, type Option } from "./Dropdown";
import { humanize } from "../lib/format";
import styles from "./FilterBar.module.css";

// Mirrors the backend enums (app/storage/models.py). Labels are humanized.
const TEAMS = [
  "engineering",
  "sales",
  "product",
  "marketing",
  "design",
  "finance",
  "operations",
];
const SENIORITY = ["intern", "entry", "mid", "senior", "staff"];
const EMPLOYMENT = ["full_time", "internship", "contract"];
const WORK_MODE = ["onsite", "hybrid", "remote"];

const toOptions = (values: string[]): Option[] =>
  values.map((v) => ({ value: v, label: humanize(v) }));

export interface FilterState {
  team: string[];
  seniority_level: string[];
  employment_type: string[];
  work_mode: string[];
  // Location is a single "city|state_region" pair selected from seen jobs.
  location: string[];
}

export const EMPTY_FILTERS: FilterState = {
  team: [],
  seniority_level: [],
  employment_type: [],
  work_mode: [],
  location: [],
};

export function FilterBar({
  filters,
  onChange,
  locationOptions,
  totalLabel,
}: {
  filters: FilterState;
  onChange: (next: FilterState) => void;
  locationOptions: Option[];
  totalLabel: string;
}) {
  const set = (key: keyof FilterState) => (next: string[]) =>
    onChange({ ...filters, [key]: next });

  return (
    <div className={styles.bar}>
      <div className={styles.filters}>
        <Dropdown
          label="Team"
          options={toOptions(TEAMS)}
          selected={filters.team}
          onChange={set("team")}
        />
        <Dropdown
          label="Seniority"
          options={toOptions(SENIORITY)}
          selected={filters.seniority_level}
          onChange={set("seniority_level")}
        />
        <Dropdown
          label="Type"
          options={toOptions(EMPLOYMENT)}
          selected={filters.employment_type}
          onChange={set("employment_type")}
        />
        <Dropdown
          label="Work mode"
          options={toOptions(WORK_MODE)}
          selected={filters.work_mode}
          onChange={set("work_mode")}
        />
        <Dropdown
          label="Location"
          options={locationOptions}
          selected={filters.location}
          onChange={set("location")}
        />
      </div>
      <span className={styles.count}>{totalLabel}</span>
    </div>
  );
}
