import { useEffect, useRef } from "react";
import type { Job } from "../api/types";
import {
  initial,
  salaryRange,
  shortDate,
  teamTone,
  workModeLabel,
  workModeTone,
} from "../lib/format";
import { CheckCircle, HeartFilled, HeartOutline } from "./icons";
import { Tag } from "./Tag";
import styles from "./JobDetail.module.css";
import type { MatchInfo } from "./JobCard";

// Honest, tier-specific callout copy. We speak to how strongly the résumé lines
// up — without fabricating role-specific reasons (we don't have per-role text).
const MATCH_BODY: Record<string, string> = {
  teal: "One of your strongest matches — your background lines up closely with what this role is looking for.",
  gold: "A solid match — much of your experience overlaps with what this role needs.",
  neutral: "A reasonable match — some of your experience is relevant to this role.",
};

function BulletList({ items, tone }: { items: string[]; tone: "coral" | "gold" }) {
  return (
    <div className={styles.bullets}>
      {items.map((text, i) => (
        <div className={styles.bullet} key={i}>
          <span className={`${styles.dot} ${tone === "gold" ? styles.dotGold : styles.dotCoral}`} />
          <span className={styles.bulletText}>{text}</span>
        </div>
      ))}
    </div>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section className={styles.section}>
      <div className={styles.sectionLabel}>{label}</div>
      {children}
    </section>
  );
}

export function JobDetail({
  job,
  saved,
  applied,
  match,
  onApply,
  onToggleSave,
}: {
  job: Job;
  saved: boolean;
  applied: boolean;
  match?: MatchInfo;
  onApply: () => void;
  onToggleSave: () => void;
}) {
  const employment = job.employment_type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join("-");
  const seniority = job.seniority_level.charAt(0).toUpperCase() + job.seniority_level.slice(1);
  const team = job.team.charAt(0).toUpperCase() + job.team.slice(1);

  // Switching jobs swaps the content in-place; reset the scroll to the top so a
  // new JD always starts at the header instead of wherever the last one was.
  const panelRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    panelRef.current?.scrollTo(0, 0);
  }, [job.id]);

  return (
    <div className={styles.panel} ref={panelRef}>
      <div className={styles.inner}>
        <div className={styles.head}>
          <div className={styles.companyRow}>
            <div className={styles.company}>
              <div className={styles.avatar}>{initial(job.company)}</div>
              <div>
                <div className={styles.companyName}>{job.company}</div>
                <div className={styles.companyAbout}>{job.company_about}</div>
              </div>
            </div>
            <button
              className={`${styles.saveBtn} ${saved ? styles.saveBtnOn : ""}`}
              onClick={onToggleSave}
            >
              {saved ? <HeartFilled width={15} height={15} /> : <HeartOutline width={15} height={15} />}
              {saved ? "Saved" : "Save"}
            </button>
          </div>

          <h1 className={styles.title}>{job.title}</h1>

          <div className={styles.chips}>
            <Tag tone={workModeTone(job.work_mode)}>{workModeLabel(job)}</Tag>
            <Tag>{employment}</Tag>
            <Tag>{seniority}</Tag>
            <Tag tone={teamTone(job.team)}>{team}</Tag>
          </div>

          <div className={styles.salaryRow}>
            <div className={styles.salaryWrap}>
              <span className={styles.salary}>
                {salaryRange(job.salary_min, job.salary_max)}
              </span>
              <span className={styles.posted}>· Posted {shortDate(job.posted_date)}</span>
            </div>
            {applied ? (
              <span className={styles.applied}>
                <CheckCircle width={15} height={15} />
                Applied
              </span>
            ) : (
              <button className={styles.apply} onClick={onApply}>
                Apply now
              </button>
            )}
          </div>
        </div>

        {match && (
          <div className={`${styles.matchCallout} ${styles[`callout_${match.tone}`]}`}>
            <div className={styles.matchHeading}>
              <span className={styles.matchDot} />
              {match.label} for your résumé
            </div>
            {/* Reasons are penalty explanations (seniority/education caveats); the
                positive skill overlap is carried separately as chips below. */}
            {match.reasons && match.reasons.length > 0 ? (
              <ul className={styles.reasonList}>
                {match.reasons.map((r, i) => (
                  <li className={styles.reason} key={i}>
                    {r}
                  </li>
                ))}
              </ul>
            ) : (
              <p className={styles.matchBody}>{MATCH_BODY[match.tone]}</p>
            )}
            {match.matchedRequired && match.matchedRequired.length > 0 && (
              <div className={styles.skillChips}>
                <span className={styles.skillLabel}>
                  {job.required_skills.length > 0
                    ? `Must-haves you match · ${match.matchedRequired.length} of ${job.required_skills.length}`
                    : "Skills you match"}
                </span>
                {match.matchedRequired.map((s) => (
                  <span className={styles.skillChip} key={s}>
                    {s}
                  </span>
                ))}
              </div>
            )}
            {match.matchedPreferred && match.matchedPreferred.length > 0 && (
              <div className={styles.skillChips}>
                <span className={styles.skillLabel}>Nice-to-haves you match</span>
                {match.matchedPreferred.map((s) => (
                  <span className={`${styles.skillChip} ${styles.skillChipPref}`} key={s}>
                    {s}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        <div className={styles.divider} />

        <Section label="About the role">
          <p className={styles.prose}>{job.about_role}</p>
        </Section>

        {job.responsibilities.length > 0 && (
          <Section label="What you'll do">
            <BulletList items={job.responsibilities} tone="coral" />
          </Section>
        )}

        {job.required_quals.length > 0 && (
          <Section label="What we're looking for">
            <BulletList items={job.required_quals} tone="coral" />
          </Section>
        )}

        {job.preferred_quals.length > 0 && (
          <Section label="Nice to have">
            <BulletList items={job.preferred_quals} tone="gold" />
          </Section>
        )}

        {job.benefits.length > 0 && (
          <Section label="Benefits">
            <BulletList items={job.benefits} tone="coral" />
          </Section>
        )}

        <p className={styles.eeo}>
          {job.company} is an equal-opportunity employer. They celebrate diversity
          and are committed to an inclusive hiring process for all candidates.
        </p>
      </div>
    </div>
  );
}
