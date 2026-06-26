import type { Job } from "../api/types";
import {
  jobMeta,
  salaryRange,
  teamTone,
  workModeLabel,
  workModeTone,
  type Tone,
} from "../lib/format";
import { HeartFilled, HeartOutline } from "./icons";
import { Tag } from "./Tag";
import styles from "./JobCard.module.css";

export interface MatchInfo {
  label: string;
  tone: Tone;
  // Backend-supplied explainability (personalized path). The card shows only the
  // label/tone; JobDetail renders these. Skill matches are split into must-have vs
  // nice-to-have so the detail view can weight required hits.
  reasons?: string[];
  matchedRequired?: string[];
  matchedPreferred?: string[];
}

export function JobCard({
  job,
  selected,
  saved,
  match,
  onSelect,
  onToggleSave,
}: {
  job: Job;
  selected: boolean;
  saved: boolean;
  match?: MatchInfo;
  onSelect: () => void;
  onToggleSave: () => void;
}) {
  return (
    <button
      className={`${styles.card} ${selected ? styles.selected : ""}`}
      onClick={onSelect}
      aria-pressed={selected}
    >
      <div className={styles.titleRow}>
        <h3 className={styles.title}>{job.title}</h3>
        <span
          className={`${styles.heart} ${saved ? styles.heartSaved : ""}`}
          role="button"
          tabIndex={0}
          aria-label={saved ? "Remove from saved" : "Save role"}
          onClick={(e) => {
            e.stopPropagation();
            onToggleSave();
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              e.stopPropagation();
              onToggleSave();
            }
          }}
        >
          {saved ? <HeartFilled width={17} height={17} /> : <HeartOutline width={17} height={17} />}
        </span>
      </div>

      <div className={styles.meta}>{jobMeta(job)}</div>

      <div className={styles.tags}>
        <span className={styles.salary}>
          {salaryRange(job.salary_min, job.salary_max)}
        </span>
        <Tag tone={workModeTone(job.work_mode)}>{workModeLabel(job)}</Tag>
        <Tag tone={teamTone(job.team)}>
          {job.team.charAt(0).toUpperCase() + job.team.slice(1)}
        </Tag>
      </div>

      <p className={styles.summary}>{job.summary}</p>

      {match && (
        <div className={styles.matchRow}>
          <span className={`${styles.dot} ${styles[`dot_${match.tone}`]}`} />
          <span className={`${styles.matchLabel} ${styles[`m_${match.tone}`]}`}>
            {match.label}
          </span>
          <span className={styles.matchSub}>· ranked by résumé fit</span>
        </div>
      )}
    </button>
  );
}
